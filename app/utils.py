"""Shared utility functions for parsing, formatting, and validation."""

import json
from typing import Any


def parse_json_list(raw: Any, default: list | None = None) -> list[Any]:
    """Safely parse a JSON string or return existing list."""
    if not raw:
        return default if default is not None else []
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str):
        return default if default is not None else []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else (default or [])
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def parse_json_dict(raw: Any, default: dict | None = None) -> dict[str, Any]:
    """Safely parse a JSON string or return existing dict."""
    if not raw:
        return default if default is not None else {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return default if default is not None else {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else (default or {})
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def validate_safe_url(url: str | None) -> str | None:
    """Ensure URL uses only safe HTTP(S) or static relative schemes."""
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if cleaned.startswith(("http://", "https://", "/static/")):
        return cleaned
    return None


def format_minutes(total_minutes: int) -> str:
    """Format total minutes into human-readable duration strings (e.g. 1d 2h 5m)."""
    if not total_minutes:
        return "0m"
    days = total_minutes // 1440
    hours = (total_minutes % 1440) // 60
    minutes = total_minutes % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)
