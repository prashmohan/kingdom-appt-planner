"""Authentication and authorization decorators."""

import hmac
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import g, request, session

from . import database, services


def require_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator verifying event existence and admin secret via capability URL or form body.

    Populates g.event and g.admin_secret upon successful verification.
    """

    @wraps(f)
    def decorated(event_uid: str, *args, **kwargs):
        secret = request.form.get("secret") or request.args.get("secret")
        db = database.get_db()
        event = services.get_event_by_uid(db, event_uid)

        if event is None:
            return "Event not found", 404
        if not secret or not hmac.compare_digest(event["admin_secret"], secret):
            return "Forbidden", 403

        g.event = event
        g.admin_secret = secret
        return f(event_uid, *args, **kwargs)

    return decorated


def require_superadmin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator enforcing authenticated superadmin session."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_superadmin"):
            return "Forbidden", 403
        return f(*args, **kwargs)

    return decorated
