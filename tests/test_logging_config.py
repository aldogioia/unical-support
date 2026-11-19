"""Formato di log unico per backend, worker e beat (app/core/logging_config.py)."""
import logging
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core import logging_config

LINE = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| (\w+)\s* \| (.+?) \| (\S+) \| (.*)$')


@pytest.fixture(autouse=True)
def restore_root_logger():
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def lines(capsys):
    return [l for l in capsys.readouterr().out.splitlines() if l]


def test_every_line_has_date_without_milliseconds_level_component_and_module(capsys):
    logging_config.setup_logging('backend')
    logging.getLogger('app.services.prova').info('[WORKER] operazione completata')
    level, component, name, message = LINE.match(lines(capsys)[0]).groups()
    assert (level, component, name, message) == ('INFO', 'backend', 'app.services.prova', '[WORKER] operazione completata')


def test_errors_carry_the_full_traceback(capsys):
    logging_config.setup_logging('worker')
    try:
        raise ValueError('rotto')
    except ValueError:
        logging.getLogger('app.tasks.prova').exception('[WORKER] Errore elaborazione documento x')
    output = lines(capsys)
    assert LINE.match(output[0]).group(1) == 'ERROR'
    assert 'Traceback (most recent call last):' in output
    assert output[-1] == 'ValueError: rotto'


def test_lines_written_inside_a_celery_task_name_the_task(capsys):
    logging_config.setup_logging('worker')
    task = SimpleNamespace(name='app.tasks.email_tasks.classify_email_task',
                           request=SimpleNamespace(id='3f2a9c1e-0000-4000-8000-000000000000'))
    with patch('celery.current_task', task):
        logging.getLogger('app.tasks.email_tasks').info('classificata')
    assert LINE.match(lines(capsys)[0]).group(2) == 'worker classify_email_task[3f2a9c1e]'


def test_uvicorn_and_celery_loggers_use_the_same_format(capsys):
    logging.getLogger('uvicorn.access').addHandler(logging.StreamHandler())
    logging_config.setup_logging('backend')
    logging.getLogger('uvicorn.access').info('10.0.0.5 - "GET /api/emails/page HTTP/1.1" 200')
    logging.getLogger('celery.worker').warning('avviso')
    output = lines(capsys)
    assert [LINE.match(l).group(3) for l in output] == ['uvicorn.access', 'celery.worker']
    assert not logging.getLogger('uvicorn.access').handlers


def test_log_level_and_noisy_libraries(capsys, monkeypatch):
    monkeypatch.setenv('LOG_LEVEL', 'WARNING')
    logging_config.setup_logging('beat')
    logging.getLogger('app.x').info('non deve comparire')
    logging.getLogger('app.x').warning('deve comparire')
    output = lines(capsys)
    assert len(output) == 1 and output[0].endswith('deve comparire')
    assert LINE.match(output[0]).group(2) == 'beat'
    assert logging.getLogger('httpx').level == logging.WARNING


def test_times_are_written_in_italian_time():
    formatter = logging_config.UnicalFormatter()
    record = logging.LogRecord('x', logging.INFO, __file__, 1, 'm', None, None)
    record.created = datetime(2026, 11, 3, 11, 0, 0, tzinfo=timezone.utc).timestamp()
    assert formatter.formatTime(record) == '2026-11-03 12:00:00'


def test_celery_hands_logging_over_to_the_shared_configuration():
    from celery.signals import setup_logging
    import app.core.celery_app  # noqa: F401  registra il ricevitore
    receivers = [r[1]() for r in setup_logging.receivers]
    assert any(getattr(r, '__name__', '') == 'configure_celery_logging' for r in receivers)
