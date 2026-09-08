"""Public blueprint handling player submissions, schedules, and general user pages."""

import json
import logging
import os
import time

import markdown
from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from config import Config

from .. import database
from ..constants import DAY_FORM_CONFIG, compute_score
from ..logic import get_ordered_active_days
from ..services import (
    create_or_replace_submission,
    delete_player_submissions_and_assignments,
    get_event_by_uid,
)
from ..utils import parse_json_list, validate_safe_url

public_bp = Blueprint("public", __name__)
audit_logger = logging.getLogger("audit")


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/guide")
def guide():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out technical badges for the in-app guide
        filtered_lines = [line for line in lines if not line.strip().startswith("[![")]
        content = "".join(filtered_lines)

        # Replace local file paths with web-accessible static paths for the in-app guide
        content = content.replace("app/static/images/", "/static/images/")
        html_content = markdown.markdown(
            content, extensions=["extra", "toc", "fenced_code"]
        )
        return render_template("guide.html", content=html_content)
    except FileNotFoundError:
        return "Guide not found", 404


@public_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, "static"),
        "favicon.svg",
        mimetype="image/svg+xml",
    )


@public_bp.route("/success/<event_uid>")
def success(event_uid):
    secret = request.args.get("secret")

    player_url = url_for("public.player_form", event_uid=event_uid, _external=True)
    admin_url = url_for(
        "admin.admin_dashboard", event_uid=event_uid, secret=secret, _external=True
    )
    finalized_url = url_for(
        "public.locked_appointments", event_uid=event_uid, _external=True
    )

    return render_template(
        "success.html",
        player_url=player_url,
        admin_url=admin_url,
        finalized_url=finalized_url,
    )


@public_bp.route("/event/<event_uid>/finalized")
def locked_appointments(event_uid):
    db = database.get_db()
    event = get_event_by_uid(db, event_uid)
    if event is None:
        return "Event not found", 404

    active_days_config = json.loads(event["active_days"])
    active_days = get_ordered_active_days(active_days_config)

    # Create a dictionary from the database row for the template
    event_dict = {
        "uid": event["uid"],
        "name": event["name"],
        "active_days": active_days_config,
        "server_id": event["server_id"],
    }

    # Fetch all assignments
    assignments_raw = db.execute(
        "SELECT * FROM assignments WHERE event_uid = ?",
        (event_uid,),
    ).fetchall()

    # Fetch submissions to get player/alliance names
    submissions_raw = db.execute(
        "SELECT * FROM submissions WHERE event_uid = ?", (event_uid,)
    ).fetchall()
    submissions_map = {
        (sub["day_type"], sub["player_id"]): sub for sub in submissions_raw
    }

    # Group rich assignments by day_type
    all_assignments = {day: {} for day in active_days}
    for a in assignments_raw:
        day_type = a["day_type"]
        player_id = a["player_id"]
        if day_type in all_assignments:
            submission = submissions_map.get((day_type, player_id))
            if submission:
                all_assignments[day_type][a["slot_index"]] = {
                    "player_id": player_id,
                    "player_name": submission["player_name"],
                    "alliance_name": submission["alliance_name"],
                    "avatar_url": submission["avatar_url"],
                    "is_locked": bool(a["is_locked"]),
                }

    return render_template(
        "locked_appointments.html",
        event=event_dict,
        active_days=active_days,
        assignments=all_assignments,
    )


@public_bp.route("/event/<event_uid>")
def player_form(event_uid):
    db = database.get_db()
    event = get_event_by_uid(db, event_uid)
    if event is None:
        return "Event not found", 404

    active_days_config = json.loads(event["active_days"])
    active_days = get_ordered_active_days(active_days_config)
    # Create a dictionary from the database row
    event_dict = {
        "uid": event["uid"],
        "name": event["name"],
        "active_days": active_days_config,
        "server_id": event["server_id"],
        "slot_count": event["slot_count"] if event["slot_count"] is not None else 49,
    }

    slot_count = event_dict["slot_count"]
    slot_density = {day: [0] * slot_count for day in active_days}
    submissions = db.execute(
        "SELECT day_type, feasible_slots FROM submissions WHERE event_uid = ?",
        (event_uid,),
    ).fetchall()
    for sub in submissions:
        dt = sub["day_type"]
        if dt in slot_density and sub["feasible_slots"]:
            for s in parse_json_list(sub["feasible_slots"]):
                if isinstance(s, int) and 0 <= s < slot_count:
                    slot_density[dt][s] += 1

    return render_template(
        "player_form.html",
        event=event_dict,
        active_days=active_days,
        slot_density=slot_density,
    )


@public_bp.route("/event/<event_uid>/submit", methods=["POST"])
def submit(event_uid):
    db = database.get_db()
    event = get_event_by_uid(db, event_uid)
    if event is None:
        return "Event not found", 404

    player_id = request.form.get("player_id", "").strip()
    player_name = request.form.get("player_name", "").strip()
    alliance_name = request.form.get("alliance_name", "").strip()

    # Server-side validation
    if not player_id.isdigit():
        return "Invalid Player ID: Must be numeric", 400

    if not player_name:
        return "Invalid Player Name: Cannot be empty", 400

    audit_logger.info(
        f"SUBMISSION: Player {player_name} ({player_id}) submitted resources for event {event_uid}"
    )

    # Handle backpack screenshot upload
    backpack_url = None
    if Config.ENABLE_SCREENSHOT_UPLOAD and "backpack_screenshot" in request.files:
        file = request.files["backpack_screenshot"]
        if file and file.filename:
            # Validate file extension
            allowed_extensions = {"png", "jpg", "jpeg", "gif"}
            extension = file.filename.rsplit(".", 1)[-1].lower()
            if extension not in allowed_extensions:
                return "Invalid file type. Only images are allowed.", 400

            # Validate image header / magic bytes
            header = file.read(16)
            file.seek(0)
            is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
            is_jpeg = header.startswith(b"\xff\xd8\xff")
            is_gif = header.startswith((b"GIF87a", b"GIF89a"))
            if not (is_png or is_jpeg or is_gif):
                return (
                    "Invalid image content. Only PNG, JPEG, and GIF images are allowed.",
                    400,
                )

            # Create upload directory if it doesn't exist
            upload_dir = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(upload_dir, exist_ok=True)

            # Generate unique filename: event_uid + player_id + timestamp + original filename
            filename = secure_filename(
                f"{event_uid}_{player_id}_{int(time.time())}_{file.filename}"
            )
            file.save(os.path.join(upload_dir, filename))
            backpack_url = validate_safe_url(
                url_for("static", filename=f"uploads/{filename}")
            )

    # Delete all previous submissions and assignments for this player and event.
    delete_player_submissions_and_assignments(db, event_uid, player_id)

    # Then, insert the new submissions from the form.
    avatar_url = validate_safe_url(request.form.get("avatar_url"))

    for day_type, field_mapping in DAY_FORM_CONFIG.items():
        feasible_slots = request.form.get(f"slots-{day_type}", "[]")
        if feasible_slots == "[]":
            continue

        raw_data = {
            field: int(request.form.get(form_field) or 0)
            for field, form_field in field_mapping.items()
        }
        score = compute_score(day_type, raw_data)
        if score > 0:
            create_or_replace_submission(
                db=db,
                event_uid=event_uid,
                day_type=day_type,
                player_id=player_id,
                player_name=player_name,
                alliance_name=alliance_name,
                score=score,
                raw_data=raw_data,
                feasible_slots_json=feasible_slots,
                avatar_url=avatar_url,
                backpack_url=backpack_url,
            )

    db.commit()

    return redirect(url_for("public.submission_success"))


@public_bp.route("/submission-success")
def submission_success():
    return render_template("submission_success.html")


@public_bp.route("/event/<event_uid>/schedule")
def public_schedule(event_uid):
    db = database.get_db()
    event = get_event_by_uid(db, event_uid)
    if event is None:
        return "Event not found", 404

    active_days_config = json.loads(event["active_days"])
    active_days = get_ordered_active_days(active_days_config)

    # Create a dictionary from the database row for the template
    event_dict = {
        "uid": event["uid"],
        "name": event["name"],
        "active_days": active_days_config,
        "server_id": event["server_id"],
    }

    assignments_raw = db.execute(
        "SELECT * FROM assignments WHERE event_uid = ?", (event_uid,)
    ).fetchall()

    # Group assignments by day_type
    assignments = {day: {} for day in active_days}
    for a in assignments_raw:
        if a["day_type"] in assignments:
            assignments[a["day_type"]][a["slot_index"]] = a

    return render_template(
        "public_schedule.html",
        event=event_dict,
        active_days=active_days,
        assignments=assignments,
    )
