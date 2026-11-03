"""Remote half of deploy.py; Python standard library only. Do not run manually."""
import ast
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time

APP_SERVICES = ['backend', 'worker', 'beat', 'frontend']
PG_PATH = '/var/lib/postgresql/data'
DOCKER_SUDO = False
DOCKER_SU = False


def configure_su(config):
    """Keep file IO under the SSH user's identity, retaining root for Docker children."""
    global DOCKER_SU
    if not config.get('su'):
        return
    if config.get('sudo'):
        raise ValueError('Scegliere soltanto uno tra su e sudo')
    if os.getuid() != 0 or os.geteuid() != 0:
        raise ValueError('La modalità --su deve essere avviata tramite su root')
    owner = config.get('file_owner') or {}
    groups = owner.get('groups')
    if not isinstance(groups, list):
        raise ValueError('Identità originale SSH mancante o non valida')
    values = [owner.get('uid'), owner.get('gid'), *groups]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError('Identità originale SSH mancante o non valida')
    # Real/saved UID remain root; effective UID/GID govern creation/access of files.
    os.setgroups(owner['groups'])
    os.setegid(owner['gid'])
    os.seteuid(owner['uid'])
    DOCKER_SU = True


def docker_root_child():
    """Called only after fork, before executing a Docker command, never in the parent."""
    os.seteuid(0)
    os.setgroups([0])
    os.setgid(0)
    os.setuid(0)


def docker_command(command):
    command = list(command)
    return ['sudo', '-n', *command] if DOCKER_SUDO and command[0] == 'docker' else command


def execute(command, **kwargs):
    command = docker_command(command)
    if DOCKER_SU and command[0] == 'docker':
        kwargs['preexec_fn'] = docker_root_child
    if DOCKER_SUDO and command[:3] == ['sudo', '-n', 'docker']:
        # The helper keeps its controlling SSH tty. sudo reads passwords there,
        # separately from binary stdin/stdout (e.g. pg_dump and pg_restore).
        # Refresh before every command so a long build cannot expire the ticket.
        subprocess.run(['sudo', '-v'], check=True)
    return subprocess.run(command, **kwargs)


def run(*args, **kwargs):
    return execute(list(args), check=True, **kwargs)


def output(*args):
    return run(*args, stdout=subprocess.PIPE, text=True).stdout.strip()


def inspect_container(identifier):
    return json.loads(output('docker', 'inspect', identifier))[0]


def containers(project=None):
    command = ['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.service']
    if project:
        command += ['--filter', f'label=com.docker.compose.project={project}']
    ids = output(*command).split()
    return json.loads(output('docker', 'inspect', *ids)) if ids else []


def service_map(rows, project):
    result = {}
    for row in rows:
        labels = row['Config'].get('Labels') or {}
        if labels.get('com.docker.compose.project') != project or labels.get('com.docker.compose.oneoff', '').lower() == 'true':
            continue
        service = labels.get('com.docker.compose.service')
        if service in result:
            raise ValueError(f'Più container per {service}: risolvere l’ambiguità prima del deploy')
        result[service] = row
    return result


def named_mount(row, destination):
    mounts = [m for m in row.get('Mounts', []) if m['Destination'] == destination]
    if len(mounts) != 1 or mounts[0]['Type'] != 'volume' or not mounts[0].get('Name'):
        raise ValueError(f'Atteso volume Docker esistente per {destination}; nessuna conversione automatica')
    return mounts[0]['Name']


def environment(row):
    return dict(value.split('=', 1) for value in row['Config'].get('Env', []) if '=' in value)


def published_on_loopback(row, port, host_port):
    entries = (row.get('NetworkSettings', {}).get('Ports', {}) or {}).get(f'{port}/tcp') or []
    return any(e['HostIp'] == '127.0.0.1' and e['HostPort'] == str(host_port) for e in entries)


def discover(config):
    output('docker', 'compose', 'version')
    rows = containers(config.get('project'))
    candidates = {r['Config']['Labels']['com.docker.compose.project'] for r in rows
                  if r['Config']['Labels'].get('com.docker.compose.service') == 'db'
                  and any(m['Destination'] == PG_PATH for m in r.get('Mounts', []))}
    if len(candidates) != 1:
        raise ValueError('Installazione PostgreSQL assente o ambigua: specificare --project esistente')
    project = candidates.pop()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', project):
        raise ValueError('Nome progetto Compose non valido')
    services = service_map(rows, project)
    for name in ['db', 'redis', *APP_SERVICES]:
        if name not in services:
            raise ValueError(f'Container esistente {name} assente; questo script aggiorna installazioni già presenti')
    for name in ['db', 'redis']:
        if not services[name]['State']['Running']:
            raise ValueError(f'{name} deve essere già avviato; lo script non lo ricrea')
    label = services['backend']['Config']['Labels']
    directory = Path(config.get('remote_dir') or label['com.docker.compose.project.working_dir'])
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError('Directory remota inesistente: indicarla con --remote-dir')
    volumes = {'postgres_data': named_mount(services['db'], PG_PATH),
               'shared_uploads': named_mount(services['backend'], '/app/uploads')}
    if named_mount(services['worker'], '/app/uploads') != volumes['shared_uploads']:
        raise ValueError('Backend e worker non condividono gli upload: correggere prima il montaggio')
    for volume in volumes.values():
        output('docker', 'volume', 'inspect', volume)
    beat_mount = next((m for m in services['beat'].get('Mounts', [])
                       if m['Destination'] == '/var/lib/celery'), None)
    if beat_mount and beat_mount['Type'] != 'volume':
        raise ValueError('Stato Beat non su volume Docker: serve una migrazione manuale')
    volumes['celerybeat_data'] = beat_mount['Name'] if beat_mount else f'{project}_celerybeat_data'
    provider = environment(services['worker']).get('MAIL_PROVIDER', 'gmail_api')
    if config['mail_provider'] != 'current':
        provider = config['mail_provider']
    if provider not in {'gmail_api', 'smtp'}:
        raise ValueError('Provider email corrente non riconosciuto')
    overlays = [str(Path(p) if Path(p).is_absolute() else directory / p) for p in config['overlay']]
    for file in overlays:
        if not Path(file).is_file():
            raise ValueError(f'Overlay assente: {file}')
    # Never silently discard hand-maintained production overrides.
    previous_files = label.get('com.docker.compose.project.config_files', '').split(',')
    for file in filter(None, previous_files):
        if Path(file).name not in {'docker-compose.prod.yml', 'docker-compose.smtp.yml', 'deploy.override.json'} and file not in overlays:
            raise ValueError(f'Overlay corrente da conservare con --overlay: {file}')
    if not published_on_loopback(services['db'], 5432, 15432) or not published_on_loopback(services['redis'], 6379, 16379):
        raise ValueError('Mancano le porte loopback 15432/16379 richieste dal worker host; vedere DEPLOY.md')
    return {'remote_dir': str(directory), 'project': project, 'provider': provider,
            'docker_access': 'su' if DOCKER_SU else 'sudo' if DOCKER_SUDO else 'direct',
            'volumes': volumes, 'overlays': overlays,
            'previous_compose_files': list(filter(None, previous_files)),
            'containers': {name: row['Id'] for name, row in services.items() if name in ['db', 'redis', *APP_SERVICES]},
            'schema_upgrade_requested': config['migrate']}


def override_config(inventory, release, runtime):
    overrides = {'volumes': {}, 'services': {}}
    for name, actual in inventory['volumes'].items():
        overrides['volumes'][name] = {'name': actual}
        if name != 'celerybeat_data':
            overrides['volumes'][name]['external'] = True
    for name in APP_SERVICES:
        overrides['services'][name] = {'build': {'context': str(release / 'frontend' if name == 'frontend' else release)}}
    if inventory['provider'] == 'gmail_api':
        for name in ['backend', 'worker']:
            overrides['services'][name]['volumes'] = [
                {'type': 'bind', 'source': str(runtime / 'credentials.json'), 'target': '/app/credentials.json', 'read_only': True, 'bind': {'create_host_path': False}},
                {'type': 'bind', 'source': str(runtime / 'token.json'), 'target': '/app/token.json', 'bind': {'create_host_path': False}},
            ]
    return overrides


def compose_command(config, inventory, release, override):
    command = ['docker', 'compose', '-p', inventory['project'], '--project-directory', inventory['remote_dir']]
    env_file = Path(inventory['remote_dir']) / '.env'
    if env_file.is_file():
        command += ['--env-file', str(env_file)]
    command += ['-f', str(release / 'docker-compose.prod.yml')]
    if inventory['provider'] == 'smtp':
        command += ['-f', str(release / 'docker-compose.smtp.yml')]
    for file in inventory['overlays']:
        command += ['-f', file]
    return docker_command(command + ['-f', str(override)])


def build_services(mode):
    return {'all': APP_SERVICES, 'backend': ['backend', 'worker', 'beat'],
            'frontend': ['frontend'], 'none': []}[mode]


def copy_oauth(services, root, runtime):
    """Preserve remote runtime tokens; never use local development credentials."""
    for filename in ['credentials.json', 'token.json']:
        destination = runtime / filename
        # Prefer the running worker's refreshed token; then backend and existing files.
        found = False
        for name in ['worker', 'backend']:
            temporary = runtime / (filename + '.pending')
            # Stream the tar to Python: sudo docker cp to a host path would
            # otherwise create root-owned credential files in the user's tree.
            result = execute(['docker', 'cp', f"{services[name]}:/app/{filename}", '-'],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                try:
                    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode='r:*') as archive:
                        members = [m for m in archive if m.isfile() and Path(m.name).name == filename]
                        if len(members) != 1 or members[0].size > 1024 * 1024:
                            raise ValueError('Archivio OAuth non valido')
                        content = archive.extractfile(members[0]).read()
                    value = json.loads(content)
                    if not isinstance(value, dict) or not value:
                        raise ValueError('File OAuth vuoto')
                    if filename == 'token.json' and not value.get('refresh_token'):
                        raise ValueError('Refresh token mancante')
                    temporary.write_bytes(content)
                    temporary.chmod(0o600)
                    temporary.replace(destination)
                    found = True
                    break
                except (ValueError, OSError, tarfile.TarError):
                    temporary.unlink(missing_ok=True)
        if not found and not destination.is_file():
            source = root / filename
            if source.is_file():
                shutil.copyfile(source, destination)
        if not destination.is_file():
            raise ValueError(f'{filename} remoto assente; completare OAuth prima del deploy')
        value = json.loads(destination.read_text())
        if not isinstance(value, dict) or not value or (filename == 'token.json' and not value.get('refresh_token')):
            raise ValueError(f'{filename} remoto non valido')
        destination.chmod(0o600)


def database_backup(container, path):
    # POSTGRES_*_FILE in production; plain env only for installations that already use it.
    script = '''set -eu
    db_user="${POSTGRES_USER:-}"; db_name="${POSTGRES_DB:-}"
    [ -n "$db_user" ] || db_user="$(cat "$POSTGRES_USER_FILE")"
    [ -n "$db_name" ] || db_name="$(cat "$POSTGRES_DB_FILE")"
    if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then export PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"; fi
    exec pg_dump -U "$db_user" -d "$db_name" -Fc
    '''
    with path.open('xb') as backup:
        path.chmod(0o600)
        run('docker', 'exec', container, 'sh', '-c', script, stdout=backup)
    if not path.stat().st_size:
        raise ValueError('Backup vuoto')
    with path.open('rb') as backup:
        run('docker', 'exec', '-i', container, 'pg_restore', '--list', stdin=backup, stdout=subprocess.DEVNULL)


@contextmanager
def deployment_lock(root):
    directory = root / '.deploy'
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / 'deploy.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Un altro deploy è già in corso') from None
        yield


def release_heads(release):
    revisions, parents = set(), set()
    for file in (release / 'alembic/versions').glob('*.py'):
        for node in ast.parse(file.read_text()).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {'revision', 'down_revision'}:
                        value = ast.literal_eval(node.value)
                        if target.id == 'revision':
                            revisions.add(value)
                        elif value:
                            parents.update(value if isinstance(value, tuple) else [value])
    return sorted(revisions - parents)


def wait_ready(command, deadline):
    while True:
        try:
            result = execute(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if result.returncode == 0:
                return
        except subprocess.TimeoutExpired:
            pass
        if time.monotonic() >= deadline:
            raise ValueError('Timeout verifica avvio; controllare log e manifest del deploy')
        time.sleep(2)


def deploy(config):
    inventory = discover(config)
    # Revalidate after upload; never rely on a stale project/volume selection.
    for name in ['project', 'remote_dir', 'volumes', 'containers', 'provider']:
        if inventory[name] != config[name]:
            raise ValueError(f'Installazione cambiata durante il trasferimento ({name}); ripetere --check')
    root, release = Path(inventory['remote_dir']), Path(config['release'])
    if release.parent != root / '.deploy/releases' or not release.is_dir():
        raise ValueError('Directory di release non valida')
    with deployment_lock(root):
        runtime = root / '.deploy/runtime'
        runtime.mkdir(mode=0o700, exist_ok=True)
        runtime.chmod(0o700)
        override = release / 'deploy.override.json'
        override.write_text(json.dumps(override_config(inventory, release, runtime), indent=2))
        command = compose_command(config, inventory, release, override)
        # Validate Compose structure without emitting environment values.
        run(*command, 'config', '--quiet')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + release.name[:8]
        previous = {name: inspect_container(cid)['Image'] for name, cid in inventory['containers'].items() if name in APP_SERVICES}
        for name, image in previous.items():
            run('docker', 'image', 'tag', image, f"{inventory['project']}-{name}:rollback-{stamp}")
        selected = build_services(config['build'])
        if selected:
            print('Build sul server: ' + ', '.join(selected), flush=True)
            run(*command, 'build', *(['--no-cache'] if config['no_cache'] else []), *selected)
        if inventory['provider'] == 'gmail_api':
            # Supply required bind files for one-off checks. Refresh the snapshot
            # again once old applications are stopped, before recreating them.
            copy_oauth(inventory['containers'], root, runtime)
        expected = release_heads(release)
        image_heads = json.loads(output(*command, 'run', '--rm', '--no-deps', '--no-build', '-T', 'backend',
            'python', '-c', 'import json; from alembic.config import Config; from alembic.script import ScriptDirectory; print(json.dumps(ScriptDirectory.from_config(Config("alembic.ini")).get_heads()))'))
        if sorted(image_heads) != expected:
            raise ValueError('L’immagine backend non corrisponde alle migrazioni caricate: usare --build all o backend')
        schema_probe = ('import json; from alembic.migration import MigrationContext; '
                        'from app.db.database import engine; '
                        'c=engine.connect(); print(json.dumps(MigrationContext.configure(c).get_current_heads())); c.close()')
        current = json.loads(output(*command, 'run', '--rm', '--no-deps', '--no-build', '-T', 'backend', 'python', '-c', schema_probe))
        if sorted(current) != expected and not config['migrate']:
            raise ValueError(f'Schema {current}, codice {expected}: ripetere con --migrate. Container applicativi ancora attivi.')
        backup_dir = root / '.deploy/backups'
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        backup = backup_dir / f'{stamp}.dump'
        manifest = {**inventory, 'release': str(release), 'previous_images': previous,
                    'schema_before': current, 'schema_target': expected, 'backup': str(backup),
                    'compose_command': command, 'backup_verified': False, 'completed': False}
        manifest_path = release / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print('Arresto controllato applicazioni (PostgreSQL e Redis restano attivi).', flush=True)
        try:
            run(*command, 'stop', '--timeout', '660', *APP_SERVICES)
            database_backup(inventory['containers']['db'], backup)
            manifest['backup_verified'] = True
            manifest_path.write_text(json.dumps(manifest, indent=2))
            print(f'Backup verificato: {backup}', flush=True)
            if inventory['provider'] == 'gmail_api':
                copy_oauth(inventory['containers'], root, runtime)
            if config['migrate']:
                run(*command, 'run', '--rm', '--no-deps', '--no-build', '-T', 'backend', 'alembic', 'upgrade', 'head')
            run(*command, 'run', '--rm', '--no-deps', '--no-build', '-T', 'backend', 'alembic', 'current')
            run(*command, 'run', '--rm', '--no-deps', '--no-build', '-T', 'backend', 'alembic', 'check')
            run(*command, 'up', '-d', '--no-deps', '--no-build', '--force-recreate', 'backend', 'worker', 'frontend')
            readiness = ('import urllib.request; from sqlalchemy import text; from app.db.database import engine; '
                         'from app.core.config import settings; from redis import Redis; '
                         'urllib.request.urlopen("http://127.0.0.1:8000/",timeout=5); '
                         'c=engine.connect(); c.execute(text("SELECT 1")); c.close(); '
                         'assert Redis.from_url(settings.REDIS_URL,socket_timeout=5).ping()')
            deadline = time.monotonic() + 180
            wait_ready(command + ['exec', '-T', 'backend', 'python', '-c', readiness], deadline)
            wait_ready(command + ['exec', '-T', 'frontend', 'wget', '-q', '-O', '/dev/null', 'http://127.0.0.1/'], deadline)
            worker = service_map(containers(inventory['project']), inventory['project'])['worker']
            wait_ready(command + ['exec', '-T', 'backend', 'celery', '-A', 'app.core.celery_app', 'inspect',
                       'ping', '--timeout', '5', '--destination', 'celery@' + worker['Config']['Hostname']], deadline)
            for name in ['db', 'redis']:
                original = inspect_container(inventory['containers'][name])
                if not original['State']['Running']:
                    raise ValueError(f'{name} non più attivo: controllare il server')
            assert named_mount(inspect_container(inventory['containers']['db']), PG_PATH) == inventory['volumes']['postgres_data']
            run(*command, 'up', '-d', '--no-deps', '--no-build', '--force-recreate', 'beat')
            run(*command, 'ps')
            manifest['completed'] = True
            manifest_path.write_text(json.dumps(manifest, indent=2))
            print(f'Deploy completato. Manifest: {manifest_path}', flush=True)
        except Exception:
            # No automatic schema downgrade or restart of incompatible old images.
            execute(command + ['stop', '--timeout', '30', *APP_SERVICES])
            print(f'Deploy interrotto; database conservato. Applicazioni ferme per evitare versioni incompatibili. Consultare {manifest_path} e docs/DEPLOY.md.', file=sys.stderr)
            raise


if __name__ == '__main__':
    try:
        action, raw_config = sys.argv[1:]
        configuration = json.loads(base64.urlsafe_b64decode(raw_config))
        DOCKER_SUDO = bool(configuration.get('sudo'))
        if DOCKER_SUDO and not shutil.which('sudo'):
            raise ValueError('sudo non è installato sul server; usare --su se è disponibile l’accesso root tramite su')
        configure_su(configuration)
        if action == 'inspect':
            inventory = json.dumps(discover(configuration))
            if configuration.get('inspection_output'):
                path = Path(configuration['inspection_output'])
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as result:
                    result.write(inventory)
            else:
                print(inventory)
        elif action == 'deploy':
            deploy(configuration)
        else:
            raise ValueError('Azione non valida')
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Deploy: {exc}', file=sys.stderr)
        sys.exit(1)
