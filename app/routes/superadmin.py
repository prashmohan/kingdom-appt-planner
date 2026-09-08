"""Superadmin blueprint handling global dashboard metrics, tenant overview, and session authentication."""

import hmac

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .. import database
from ..auth import require_superadmin
from ..logic import generate_slot_labels, get_superadmin_metrics

superadmin_bp = Blueprint("superadmin", __name__)


@superadmin_bp.route("/superadmin")
def superadmin():
    secret = request.args.get("secret")
    if secret is not None:
        expected_secret = current_app.config.get("SUPERADMIN_SECRET", "")
        if hmac.compare_digest(secret, expected_secret):
            session["is_superadmin"] = True
            range_param = request.args.get("range", "all")
            return redirect(url_for("superadmin.superadmin", range=range_param))
        return "Forbidden", 403

    if session.get("is_superadmin") is True:
        range_param = request.args.get("range", "all")
        valid_range = range_param if range_param in ("1w", "2w", "4w") else "all"
        db = database.get_db()
        metrics = get_superadmin_metrics(db, time_range=valid_range)
        slot_labels = generate_slot_labels(49)
        return render_template(
            "superadmin.html",
            metrics=metrics,
            current_range=valid_range,
            slot_labels=slot_labels,
        )

    return "Forbidden", 403


@superadmin_bp.route("/superadmin/logout")
@require_superadmin
def superadmin_logout():
    session.pop("is_superadmin", None)
    return redirect(url_for("public.index"))
