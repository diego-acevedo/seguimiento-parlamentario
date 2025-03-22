import datetime as dt
import pytz
import re
import tiktoken
import unicodedata

# Basic ISO 8601 regex
ISO_DATETIME_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}"  # YYYY-MM-DD
    r"(T\d{2}:\d{2}:\d{2}"  # Thh:mm:ss
    r"(\.\d+)?"  # .microseconds (optional)
    r"(Z|[+-]\d{2}:\d{2})?)?$"  # Z or +hh:mm (optional)
)


def get_timezone():
    """
    Get the Chile timezone object.

    Returns:
        pytz.timezone: America/Santiago timezone object
    """
    return pytz.timezone("America/Santiago")


def parse_iso_datetime(s):
    """
    Parse an ISO 8601 formatted string to datetime or date object.

    Attempts to parse the string as a full datetime first, then as a date only.
    If neither parsing succeeds, returns the original string.

    Args:
        s: String to parse in ISO 8601 format

    Returns:
        datetime.datetime, datetime.date, or str: Parsed object or original string
    """
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
    """
    Recursively convert ISO 8601 datetime strings to datetime objects in nested data structures.

    Traverses dictionaries and lists recursively, converting any string that matches
    the ISO 8601 datetime format to actual datetime/date objects.

    Args:
        obj: Data structure (dict, list, or any value) to process

    Returns:
        Processed data structure with datetime strings converted to datetime objects
    """
    if isinstance(obj, dict):
        return {k: convert_datetime_strings_to_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_strings_to_datetime(item) for item in obj]
    elif isinstance(obj, str) and ISO_DATETIME_REGEX.match(obj):
        return parse_iso_datetime(obj)
    else:
        return obj


def convert_datetime_in_dict(obj):
    """
    Recursively convert datetime objects to ISO format strings in nested data structures.

    Traverses dictionaries and lists recursively, converting any datetime or date
    objects to their ISO format string representation for JSON serialization.

    Args:
        obj: Data structure (dict, list, or any value) to process

    Returns:
        Processed data structure with datetime objects converted to ISO strings
    """
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


tokenizer = tiktoken.get_encoding("cl100k_base")


def chunk_text(text, chunk_size=500, overlap=50):
    """
    Split text into overlapping chunks based on token count.

    Uses the cl100k_base tokenizer to split text into chunks of specified token size
    with configurable overlap between consecutive chunks.

    Args:
        text: Text string to chunk
        chunk_size: Maximum number of tokens per chunk (default: 500)
        overlap: Number of tokens to overlap between chunks (default: 50)

    Returns:
        list: List of text chunks as strings
    """
    tokens = tokenizer.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + chunk_size
        chunk = tokens[start:end]
        chunks.append(tokenizer.decode(chunk))
        start += chunk_size - overlap

    return chunks


def batch(iterable, size=96):
    """
    Split an iterable into batches of specified size.

    Generator function that yields consecutive batches from the input iterable.

    Args:
        iterable: Any sequence or iterable to batch
        size: Maximum size of each batch (default: 96)

    Yields:
        Batches of the original iterable with specified maximum size
    """
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def normalize_text(text):
    """
    Normalize text by removing accents and converting to lowercase.

    Performs Unicode normalization (NFD) to separate base characters from
    combining marks (accents), then removes the combining marks and converts
    to lowercase for consistent text processing.

    Args:
        text: Text string to normalize

    Returns:
        str: Normalized text without accents in lowercase
    """
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )
