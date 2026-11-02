"""Superadmin blueprint handling global dashboard metrics, tenant overview, and session authentication."""

import hmac
import sqlite3

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
        db.row_factory = sqlite3.Row
        metrics = get_superadmin_metrics(db, time_range=valid_range)
        slot_labels = generate_slot_labels(49)
        reports_rows = db.execute(
            """
            SELECT id, COALESCE(report_type, 'translation') AS report_type, lang, page_url,
                   original_text, suggested_text, context_notes, status, created_at
            FROM translation_reports
            ORDER BY CASE WHEN status = 'Open' THEN 0 ELSE 1 END, created_at DESC
            """
        ).fetchall()
        translation_reports = [dict(r) for r in reports_rows]
        open_reports_count = sum(
            1 for r in translation_reports if r["status"] == "Open"
        )
        return render_template(
            "superadmin.html",
            metrics=metrics,
            current_range=valid_range,
            slot_labels=slot_labels,
            translation_reports=translation_reports,
            open_reports_count=open_reports_count,
        )

    return "Forbidden", 403


@superadmin_bp.route(
    "/superadmin/translation_reports/<int:report_id>/resolve", methods=["POST"]
)
@require_superadmin
def resolve_translation_report(report_id: int):
    db = database.get_db()
    row = db.execute(
        "SELECT status FROM translation_reports WHERE id = ?", (report_id,)
    ).fetchone()
    if row is None:
        return "Report not found", 404
    current_status = row[0]
    new_status = "Resolved" if current_status == "Open" else "Open"
    db.execute(
        "UPDATE translation_reports SET status = ? WHERE id = ?",
        (new_status, report_id),
    )
    db.commit()
    range_param = request.args.get("range", "all")
    return redirect(url_for("superadmin.superadmin", range=range_param))


@superadmin_bp.route(
    "/superadmin/translation_reports/<int:report_id>/delete", methods=["POST"]
)
@require_superadmin
def delete_translation_report(report_id: int):
    db = database.get_db()
    db.execute("DELETE FROM translation_reports WHERE id = ?", (report_id,))
    db.commit()
    range_param = request.args.get("range", "all")
    return redirect(url_for("superadmin.superadmin", range=range_param))


@superadmin_bp.route("/superadmin/logout")
@require_superadmin
def superadmin_logout():
    session.pop("is_superadmin", None)
    return redirect(url_for("public.index"))
