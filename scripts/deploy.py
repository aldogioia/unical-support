#!/usr/bin/env python3
"""Upload the working tree through SSH and deploy against existing production data."""
import argparse
import base64
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


def ssh_args(args):
    result = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
              '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=15',
              '-o', 'ServerAliveCountMax=3']
    if args.identity:
        result += ['-o', 'IdentitiesOnly=yes', '-i', str(Path(args.identity).expanduser())]
    if args.jump_identity:
        proxy = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                 '-o', 'ConnectTimeout=15', '-o', 'IdentitiesOnly=yes',
                 '-i', str(Path(args.jump_identity).expanduser()),
                 '-W', '%h:%p', args.jump_host]
        result += ['-o', 'ProxyCommand=' + shlex.join(proxy)]
    else:
        result += ['-J', args.jump_host]
    return result + ['--', args.host]


def encoded(config):
    return base64.urlsafe_b64encode(json.dumps(config).encode()).decode()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='UnicalSupport', help='Alias SSH di destinazione')
    p.add_argument('--identity', help='Chiave SSH della destinazione')
    p.add_argument('--jump-identity', help='Chiave SSH del jump host (evita troppi tentativi dall’agent)')
    p.add_argument('--jump-host', default='UnicalSupportJump')
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
        'remote_dir', 'project', 'build', 'no_cache', 'migrate', 'mail_provider', 'overlay')}
    if args.dry_run:
        print(json.dumps({'host': args.host, **config,
                          'source_files': len(list(payload_files())),
                          'database': 'solo volume esistente; backup obbligatorio; nessuna ricreazione',
                          'build_location': 'server remoto',
                          'secrets': 'solo quelli già sul server'}, indent=2, ensure_ascii=False))
        return 0
    remote_source = (ROOT / 'scripts/deploy_remote.py').read_bytes()
    inspection = subprocess.run(ssh_args(args) + [shlex.join([
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
        subprocess.run(ssh_args(args) + [upload], stdin=archive, check=True)
    subprocess.run(ssh_args(args) + [shlex.join([
        'python3', str(release / 'scripts/deploy_remote.py'), 'deploy', encoded(config)])], check=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        print(f'Deploy interrotto: {exc}', file=sys.stderr)
        sys.exit(1)
