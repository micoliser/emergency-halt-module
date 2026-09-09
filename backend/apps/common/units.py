"""
Big-integer + timestamp helpers.

On-chain `u256` values (bonds) exceed JS `Number.MAX_SAFE_INTEGER`, so they
cross the API as decimal strings. The frontend formats from the string.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

JS_SAFE_MAX = 2**53 - 1
GEN_DECIMALS = 18


def to_int(value: Any, default: int = 0) -> int:
    """Coerce an on-chain scalar (int / decimal str / hex str) to int."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    try:
        if text.lower().startswith("0x"):
            return int(text, 16)
        return int(text)
    except ValueError:
        return default


def to_amount_str(value: Any) -> str:
    """Store/emit u256 amounts as decimal strings."""
    return str(to_int(value))


def format_gen(value: Any, decimals: int = GEN_DECIMALS) -> str:
    """
    Format a wei-style integer as a trimmed decimal string.

    >>> format_gen("1000000000000000000")
    '1'
    >>> format_gen("1500000000000000000")
    '1.5'
    """
    amount = to_int(value)
    negative = amount < 0
    amount = abs(amount)
    scale = 10**decimals
    whole, frac = divmod(amount, scale)
    text = str(whole)
    if frac:
        text = f"{text}.{str(frac).rjust(decimals, '0').rstrip('0')}"
    return f"-{text}" if negative else text


def unix_to_datetime(value: Any) -> datetime | None:
    """Convert an on-chain unix-seconds timestamp to an aware datetime."""
    seconds = to_int(value, default=0)
    if seconds <= 0:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def json_safe(value: Any) -> Any:
    """
    Make a decoded calldata value safe for JSONField storage and JS clients:
    ints beyond the JS safe range become strings, bytes become hex.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value if abs(value) <= JS_SAFE_MAX else str(value)
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    if isinstance(value, Decimal):
        return json_safe(int(value))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (str, float)):
        return value
    return str(value)


def normalize_address(value: Any) -> str:
    """Normalize an address-ish value to lowercase 0x-prefixed 20-byte hex."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    raw = value.as_hex if hasattr(value, "as_hex") else value
    text = str(raw).strip()
    if not text:
        return ""
    if not text.startswith("0x") and not text.startswith("0X"):
        text = "0x" + text
    return "0x" + text[2:].lower().rjust(40, "0")


def string_list(value: Any) -> list[str]:
    """Coerce an on-chain list field to a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [part for part in value.split("|") if part]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return []
