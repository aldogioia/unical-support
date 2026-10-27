from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re


def received_timestamp(internal_ms=None, internal_imap=None, header_date=None):
    try:
        if internal_ms is not None:
            return datetime.fromtimestamp(int(internal_ms) / 1000, timezone.utc)
        if internal_imap:
            match = re.search(rb'INTERNALDATE "([^"]+)"', internal_imap)
            if match:
                return datetime.strptime(match[1].decode('ascii'), '%d-%b-%Y %H:%M:%S %z').astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        pass
    try:
        date = parsedate_to_datetime(header_date or '')
        return (date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date).astimezone(timezone.utc)
    except (ValueError, TypeError, IndexError):
        return datetime.now(timezone.utc)
