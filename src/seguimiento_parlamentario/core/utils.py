import datetime as dt
import re

# Basic ISO 8601 regex
ISO_DATETIME_REGEX = re.compile(
    r'^\d{4}-\d{2}-\d{2}'         # YYYY-MM-DD
    r'(T\d{2}:\d{2}:\d{2}'        # Thh:mm:ss
    r'(\.\d+)?'                   # .microseconds (optional)
    r'(Z|[+-]\d{2}:\d{2})?)?$'    # Z or +hh:mm (optional)
)

def parse_iso_datetime(s):
    try:
        # Attempt full datetime with optional timezone
        return dt.datetime.fromisoformat(s)
    except ValueError:
        try:
            # Attempt date only
            return dt.date.fromisoformat(s)
        except ValueError:
            return s  # not a valid date or datetime

def convert_datetime_strings_to_datetime(obj):
    if isinstance(obj, dict):
        return {k: convert_datetime_strings_to_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_strings_to_datetime(item) for item in obj]
    elif isinstance(obj, str) and ISO_DATETIME_REGEX.match(obj):
        return parse_iso_datetime(obj)
    else:
        return obj

def convert_datetime_in_dict(obj):
    if isinstance(obj, dict):
        return {k: convert_datetime_in_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_in_dict(item) for item in obj]
    elif isinstance(obj, dt.datetime):
        return obj.isoformat()
    elif isinstance(obj, dt.date):
        return obj.isoformat()
    else:
        return obj