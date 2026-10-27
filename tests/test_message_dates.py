from datetime import datetime, timezone
from app.core.message_dates import received_timestamp


def test_provider_arrival_dates_are_utc_and_prefer_internal_server_timestamp():
    expected = datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc)
    assert received_timestamp(internal_ms=str(int(expected.timestamp() * 1000))) == expected
    assert received_timestamp(internal_imap=b'1 (UID 7 INTERNALDATE "26-Oct-2026 13:30:00 +0100")') == expected
    assert received_timestamp(header_date='Mon, 26 Oct 2026 13:30:00 +0100') == expected


def test_missing_and_invalid_provider_dates_fall_back_to_utc_intake_time():
    before = datetime.now(timezone.utc)
    value = received_timestamp(internal_ms='invalid', header_date='bad date')
    assert before <= value <= datetime.now(timezone.utc)
