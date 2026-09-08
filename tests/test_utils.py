"""Unit tests for app/utils.py."""

from app.utils import (
    format_minutes,
    parse_json_dict,
    parse_json_list,
    validate_safe_url,
)


def test_parse_json_list():
    assert parse_json_list(None) == []
    assert parse_json_list("") == []
    assert parse_json_list("not-json") == []
    assert parse_json_list('{"a": 1}') == []
    assert parse_json_list("[1, 2, 3]") == [1, 2, 3]
    assert parse_json_list([4, 5]) == [4, 5]
    assert parse_json_list("invalid", default=[99]) == [99]


def test_parse_json_dict():
    assert parse_json_dict(None) == {}
    assert parse_json_dict("") == {}
    assert parse_json_dict("not-json") == {}
    assert parse_json_dict("[1, 2]") == {}
    assert parse_json_dict('{"speedups": 100}') == {"speedups": 100}
    assert parse_json_dict({"speedups": 50}) == {"speedups": 50}
    assert parse_json_dict("invalid", default={"fallback": True}) == {"fallback": True}


def test_validate_safe_url():
    assert validate_safe_url(None) is None
    assert validate_safe_url("") is None
    assert validate_safe_url("   ") is None
    assert validate_safe_url("javascript:alert(1)") is None
    assert validate_safe_url("data:text/html;base64,...") is None
    assert (
        validate_safe_url("https://example.com/avatar.png")
        == "https://example.com/avatar.png"
    )
    assert (
        validate_safe_url("http://example.com/avatar.png")
        == "http://example.com/avatar.png"
    )
    assert (
        validate_safe_url("/static/default_avatar.png") == "/static/default_avatar.png"
    )


def test_format_minutes_in_utils():
    assert format_minutes(0) == "0m"
    assert format_minutes(30) == "30m"
    assert format_minutes(60) == "1h"
    assert format_minutes(90) == "1h 30m"
    assert format_minutes(1440) == "1d"
    assert format_minutes(1441) == "1d 1m"
    assert format_minutes(1500) == "1d 1h"
