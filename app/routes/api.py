"""API blueprint handling event creation and third-party player lookup proxies."""

import json
import logging
import secrets

from flask import Blueprint, jsonify, redirect, request, url_for

import app

from .. import database
from ..logic import generate_short_uid, validate_custom_slug

api_bp = Blueprint("api", __name__)
audit_logger = logging.getLogger("audit")


@api_bp.route("/api/proxy/player", methods=["POST"])
def proxy_player():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Missing or invalid JSON payload"}), 400

    fid = data.get("fid")
    if not fid:
        return jsonify({"error": "Missing fid"}), 400

    fid_str = str(fid).strip()
    if not fid_str.isdigit():
        return jsonify({"error": "Invalid fid: must be numeric"}), 400

    try:
        player_info = app.fetch_player_info(fid_str)
    except Exception as e:  # noqa: BLE001
        audit_logger.error(f"Error fetching player info for {fid_str}: {e}")
        return jsonify({"error": "Internal error"}), 500

    if player_info:
        return jsonify(player_info)
    else:
        return jsonify({"error": "Player not found or API error"}), 404


@api_bp.route("/create", methods=["POST"])
def create_event():
    event_name = request.form.get("event_name", "").strip()
    if not event_name:
        event_name = "Untitled Event"

    research_day = request.form.get("research_day", "5")
    try:
        slot_count = int(request.form.get("slot_count", "49"))
        if slot_count not in [48, 49]:
            slot_count = 49
    except ValueError:
        slot_count = 49

    db = database.get_db()

    # Handle custom slug or auto-generated short UID
    custom_slug = request.form.get("custom_slug", "").strip()
    if custom_slug:
        is_valid, err_msg = validate_custom_slug(custom_slug, db)
        if not is_valid:
            return err_msg, 400
        uid = custom_slug
    else:
        # Generate unique short UID with collision check
        while True:
            candidate_uid = generate_short_uid(8)
            exists = db.execute(
                "SELECT 1 FROM events WHERE uid = ?", (candidate_uid,)
            ).fetchone()
            if not exists:
                uid = candidate_uid
                break

    admin_secret = secrets.token_urlsafe(16)

    active_days = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": int(research_day),
    }

    raw_server_id = request.form.get("server_id", "").strip()
    server_id = None
    if raw_server_id:
        try:
            parsed_id = int(raw_server_id)
            if parsed_id > 0:
                server_id = parsed_id
        except ValueError:
            server_id = None

    db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id) VALUES (?, ?, ?, ?, ?, ?)",
        (
            uid,
            event_name,
            json.dumps(active_days),
            admin_secret,
            slot_count,
            server_id,
        ),
    )
    db.commit()

    return redirect(url_for("public.success", event_uid=uid, secret=admin_secret))
