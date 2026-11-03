#!/usr/bin/env python3
"""Upload the working tree through SSH and deploy against existing production data."""
import argparse
import base64
from contextlib import contextmanager
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOTS = (
    'app', 'alembic', 'alembic.ini', 'frontend', 'scripts', 'docs', 'create_user.py', 'Dockerfile',
    'docker-compose.prod.yml', 'docker-compose.smtp.yml',
    'requirements-base.txt', 'requirements-worker.txt', '.dockerignore',
)
EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', 'dist', '__pycache__',
            '.angular', '.pytest_cache', 'coverage', 'uploads', 'secrets', '.deploy'}


def payload_files(root=ROOT):
    """Explicit allowlist; credentials and runtime data never leave this computer."""
    for name in PAYLOAD_ROOTS:
        source = root / name
        paths = sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in paths:
            relative = path.relative_to(root)
            if (not path.is_file() or path.is_symlink()
                    or any(p in EXCLUDED for p in relative.parts)
                    or any(p.startswith('.env') for p in relative.parts)
                    or path.name in {'credentials.json', 'token.json', '.DS_Store'}
                    or path.suffix in {'.pyc', '.log', '.dump', '.pem', '.key'}):
                continue
            yield path, relative


def ssh_args(args, control_path=None):
    batch_mode = 'no' if args.interactive_ssh else 'yes'
    # The target also waits for the jump authentication before its SSH banner.
    timeout = '180' if args.interactive_ssh else '15'
    result = ['ssh', '-o', f'BatchMode={batch_mode}', '-o', f'ConnectTimeout={timeout}',
              '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=15',
              '-o', 'ServerAliveCountMax=3']
    if args.identity:
        result += ['-o', 'IdentitiesOnly=yes', '-i', str(Path(args.identity).expanduser())]
    # Explicit proxy: -J does not propagate BatchMode to the jump process.
    proxy = ['ssh', '-o', f'BatchMode={batch_mode}', '-o', 'StrictHostKeyChecking=yes',
             '-o', f'ConnectTimeout={timeout}']
    if args.jump_identity:
        proxy += ['-o', 'IdentitiesOnly=yes', '-i', str(Path(args.jump_identity).expanduser())]
    proxy += ['-W', '%h:%p', args.jump_host]
    result += ['-o', 'ProxyCommand=' + shlex.join(proxy)]
    if control_path is not None:
        result += ['-o', 'ControlMaster=auto', '-o', 'ControlPersist=300',
                   '-o', f'ControlPath={control_path}']
    return result + ['--', args.host]


@contextmanager
def ssh_connection(args):
    """Authenticate before piping source/archive data; reuse and close our own master."""
    with tempfile.TemporaryDirectory(prefix='unical-ssh-') as directory:
        command = ssh_args(args, Path(directory) / 'control')
        try:
            print(f'Connessione a {args.host} tramite {args.jump_host}…', flush=True)
            # Passwords are read by OpenSSH from /dev/tty, never by Python/stdin.
            subprocess.run(command[:-2] + ['-M', '-N', '-f'] + command[-2:],
                           stdin=subprocess.DEVNULL, check=True)
            yield command
        finally:
            # -O exit only closes this private socket; it never starts a new login.
            subprocess.run(command[:-2] + ['-O', 'exit'] + command[-2:],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)


def encoded(config):
    return base64.urlsafe_b64encode(json.dumps(config).encode()).decode()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='UnicalSupport', help='Alias SSH di destinazione')
    p.add_argument('--identity', help='Chiave SSH della destinazione')
    p.add_argument('--jump-identity', help='Chiave SSH del jump host (evita troppi tentativi dall’agent)')
    p.add_argument('--jump-host', default='UnicalSupportJump')
    p.add_argument('--interactive-ssh', action='store_true',
                   help='Consenti password/passphrase dal terminale per jump e destinazione')
    privileges = p.add_mutually_exclusive_group()
    privileges.add_argument('--sudo', action='store_true', help='Esegui Docker remoto tramite sudo, con terminale per la password')
    privileges.add_argument('--su', action='store_true', help='Usa su root sul server, con richiesta della password di root')
    p.add_argument('--remote-dir', help='Directory esistente sul server; altrimenti ricavata dai container')
    p.add_argument('--project', help='Nome Compose esistente; obbligatorio se ambiguo')
    p.add_argument('--build', choices=['all', 'backend', 'frontend', 'none'], default='all')
    p.add_argument('--no-cache', action='store_true', help='Build senza cache (richiede --build diverso da none)')
    p.add_argument('--migrate', action='store_true', help='Esegui alembic upgrade head dopo il backup')
    p.add_argument('--mail-provider', choices=['current', 'gmail_api', 'smtp'], default='current')
    p.add_argument('--overlay', action='append', default=[], help='File Compose aggiuntivo già sul server (ripetibile)')
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='Piano locale, senza SSH né modifiche')
    modes.add_argument('--check', action='store_true', help='Inventario remoto in sola lettura, senza upload/deploy')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.no_cache and args.build == 'none':
        parser().error('--no-cache non è compatibile con --build none')
    if any(value.startswith('-') for value in [args.host, args.jump_host]):
        parser().error('Alias SSH non valido')
    config = {key: getattr(args, key) for key in (
        'remote_dir', 'project', 'build', 'no_cache', 'migrate', 'mail_provider', 'overlay', 'sudo', 'su')}
    if args.dry_run:
        print(json.dumps({'host': args.host, **config,
                          'interactive_ssh': args.interactive_ssh,
                          'source_files': len(list(payload_files())),
                          'database': 'solo volume esistente; backup obbligatorio; nessuna ricreazione',
                          'build_location': 'server remoto',
                          'secrets': 'solo quelli già sul server'}, indent=2, ensure_ascii=False))
        return 0
    with ssh_connection(args) as connection:
        return deploy_over_ssh(args, config, connection)


def tty_connection(connection):
    return connection[:-2] + ['-tt'] + connection[-2:]


def helper_command(helper, action, config):
    command = shlex.join(['python3', str(helper), action, encoded(config)])
    if config.get('su'):
        return shlex.join(['su', '--login', 'root', '--command', 'exec ' + command])
    return command


def remote_file_owner(connection):
    script = ('import os,json; print(json.dumps({"uid":os.getuid(),'
              '"gid":os.getgid(),"groups":os.getgroups()}))')
    result = subprocess.run(connection + [shlex.join(['python3', '-c', script])],
                            stdout=subprocess.PIPE, check=True)
    return json.loads(result.stdout)


def inspect_with_privileges(config, connection, source):
    """Keep the authentication terminal separate from source and JSON output."""
    result = subprocess.run(connection + ['mktemp -d /tmp/unical-deploy.XXXXXXXXXX'],
                            stdout=subprocess.PIPE, check=True, text=True)
    directory = Path(result.stdout.strip())
    if directory.parent != Path('/tmp') or not directory.name.startswith('unical-deploy.'):
        raise ValueError('Directory temporanea remota non valida')
    helper, inventory_file = directory / 'inspect.py', directory / 'inventory.json'
    try:
        subprocess.run(connection + ['umask 077; cat > ' + shlex.quote(str(helper))], input=source, check=True)
        probe = {**config, 'inspection_output': str(inventory_file)}
        subprocess.run(tty_connection(connection) + [helper_command(helper, 'inspect', probe)], check=True)
        result = subprocess.run(connection + [shlex.join(['cat', str(inventory_file)])],
                                stdout=subprocess.PIPE, check=True)
        return json.loads(result.stdout)
    finally:
        # Delete only the two files we created, never recursively remove a tree.
        cleanup = ('from pathlib import Path; p=Path(' + repr(str(directory)) + '); '
                   '(p/"inspect.py").unlink(missing_ok=True); '
                   '(p/"inventory.json").unlink(missing_ok=True); p.rmdir()')
        subprocess.run(connection + [shlex.join(['python3', '-c', cleanup])],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def deploy_over_ssh(args, config, connection):
    remote_source = (ROOT / 'scripts/deploy_remote.py').read_bytes()
    if args.su:
        config['file_owner'] = remote_file_owner(connection)
    if args.sudo or args.su:
        inventory = inspect_with_privileges(config, connection, remote_source)
    else:
        inspection = subprocess.run(connection + [shlex.join([
            'python3', '-', 'inspect', encoded(config)])], input=remote_source,
            stdout=subprocess.PIPE, check=True)
        inventory = json.loads(inspection.stdout)
    print(json.dumps(inventory, indent=2, ensure_ascii=False), flush=True)
    if args.check:
        return 0
    config.update(inventory)
    release_id = uuid.uuid4().hex
    # The upload is extracted in a fresh directory, never over existing source/data.
    release = Path(inventory['remote_dir']) / '.deploy/releases' / release_id
    config['release'] = str(release)
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive, mode='w:gz') as tar:
            for path, relative in payload_files():
                tar.add(path, arcname=str(relative), recursive=False)
        archive.seek(0)
        upload = 'umask 077; mkdir -p {0} && tar -xzf - -C {0}'.format(shlex.quote(str(release)))
        subprocess.run(connection + [upload], stdin=archive, check=True)
    execution = tty_connection(connection) if args.sudo or args.su else connection
    subprocess.run(execution + [helper_command(release / 'scripts/deploy_remote.py', 'deploy', config)], check=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        hint = ('Per accessi SSH con password usare --interactive-ssh.' if exc.returncode == 255
                else 'Controllare l’errore remoto precedente (Docker, su/sudo o prerequisiti).')
        print(f'Deploy interrotto: SSH/comando remoto terminato con codice {exc.returncode}. '
              + hint, file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError) as exc:
        print(f'Deploy interrotto: {exc}', file=sys.stderr)
        sys.exit(1)
