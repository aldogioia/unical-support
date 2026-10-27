"""Derive worker URLs for the VPS loopback ports without printing credentials."""
import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def prepare_secrets(directory: Path):
    pending = []
    for name, port in [('database_url', 15432), ('redis_url', 16379)]:
        url = urlsplit((directory / name).read_text().strip())
        if not url.scheme or not url.hostname:
            raise ValueError(f'URL non valido nel secret {name}')
        userinfo, separator, _ = url.netloc.rpartition('@')
        netloc = (userinfo + separator if separator else '') + f'127.0.0.1:{port}'
        pending.append((directory / f'{name}_host', urlunsplit(url._replace(netloc=netloc))))

    for path, value in pending:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(value + '\n')
        print(f'Creato {path} (permessi 600).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secrets-dir', type=Path, default=Path('/home/operatore/secrets'))
    prepare_secrets(parser.parse_args().secrets_dir)
