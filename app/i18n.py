"""Internationalization (i18n) helpers and catalog loader for kvk-appt."""

import json
import logging
import os
from typing import Any

from flask import g, has_request_context, request

logger = logging.getLogger(__name__)

LANG_COOKIE_NAME = "kvk_lang"
DEFAULT_LANG = "en"

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {
        "code": "en",
        "name": "English",
        "native": "English",
        "dir": "ltr",
        "flag": "🇬🇧",
    },
    "es": {
        "code": "es",
        "name": "Spanish",
        "native": "Español",
        "dir": "ltr",
        "flag": "🇪🇸",
    },
    "zh": {
        "code": "zh",
        "name": "Simplified Chinese",
        "native": "简体中文",
        "dir": "ltr",
        "flag": "🇨🇳",
    },
    "ar": {
        "code": "ar",
        "name": "Arabic",
        "native": "العربية",
        "dir": "rtl",
        "flag": "🇸🇦",
    },
    "ko": {
        "code": "ko",
        "name": "Korean",
        "native": "한국어",
        "dir": "ltr",
        "flag": "🇰🇷",
    },
    "pt": {
        "code": "pt",
        "name": "Portuguese",
        "native": "Português",
        "dir": "ltr",
        "flag": "🇧🇷",
    },
    "tr": {
        "code": "tr",
        "name": "Turkish",
        "native": "Türkçe",
        "dir": "ltr",
        "flag": "🇹🇷",
    },
}

_CATALOGS: dict[str, dict[str, str]] = {}


def load_catalogs() -> dict[str, dict[str, str]]:
    """Load JSON translation catalogs from app/translations/."""
    global _CATALOGS
    if _CATALOGS:
        return _CATALOGS

    translations_dir = os.path.join(os.path.dirname(__file__), "translations")
    loaded: dict[str, dict[str, str]] = {}
    for code in SUPPORTED_LANGUAGES:
        filepath = os.path.join(translations_dir, f"{code}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    loaded[code] = {str(k): str(v) for k, v in data.items()}
                else:
                    loaded[code] = {}
        except FileNotFoundError:
            logger.warning(f"Translation catalog not found: {filepath}")
            loaded[code] = {}
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to load translation catalog {filepath}: {e}")
            loaded[code] = {}

    _CATALOGS = loaded
    return _CATALOGS


def normalize_lang(raw_lang: str | None) -> str | None:
    """Normalize a language tag (e.g. 'zh-CN', 'es_MX', 'ar-SA') to a supported code."""
    if not raw_lang or not isinstance(raw_lang, str):
        return None
    cleaned = raw_lang.strip().lower().replace("_", "-")
    if not cleaned:
        return None
    if cleaned in SUPPORTED_LANGUAGES:
        return cleaned
    primary = cleaned.split("-")[0]
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return None


def get_locale() -> str:
    """Resolve active language code for the current request."""
    if not has_request_context():
        return DEFAULT_LANG

    cached = getattr(g, "_locale", None)
    if cached:
        return cached

    # 1. Explicit query parameter (?lang=xx)
    query_lang = normalize_lang(request.args.get("lang"))
    if query_lang:
        g._locale = query_lang
        g._set_lang_cookie = query_lang
        return query_lang

    # 2. Persisted language cookie
    cookie_lang = normalize_lang(request.cookies.get(LANG_COOKIE_NAME))
    if cookie_lang:
        g._locale = cookie_lang
        return cookie_lang

    # 3. Browser Accept-Language header
    if request.accept_languages:
        for raw_tag, _weight in request.accept_languages:
            matched = normalize_lang(raw_tag)
            if matched:
                g._locale = matched
                return matched

    g._locale = DEFAULT_LANG
    return DEFAULT_LANG


def get_text_dir(lang: str | None = None) -> str:
    """Return 'rtl' for right-to-left languages (Arabic) or 'ltr' otherwise."""
    active = lang or get_locale()
    meta = SUPPORTED_LANGUAGES.get(active, SUPPORTED_LANGUAGES[DEFAULT_LANG])
    return meta.get("dir", "ltr")


def translate(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Translate a key using the active or specified locale with English fallback."""
    catalogs = load_catalogs()
    active_lang = lang or get_locale()

    lang_catalog = catalogs.get(active_lang, {})
    en_catalog = catalogs.get(DEFAULT_LANG, {})

    template = lang_catalog.get(key)
    if template is None:
        template = en_catalog.get(key, key)

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            return template
    return template
