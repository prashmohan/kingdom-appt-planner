"""Admin blueprint handling event administration, distribution, assignment, import/export, and logs."""

import csv
import datetime
import io
import json
import logging
import os

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

import app

from .. import database, logic
from ..auth import require_admin
from ..constants import compute_score
from ..logic import (
    compute_event_insights,
    generate_slot_labels,
    get_ordered_active_days,
)
from ..utils import format_minutes, parse_json_dict, validate_safe_url

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
audit_logger = logging.getLogger("audit")


@admin_bp.route("/<event_uid>")
@require_admin
def admin_dashboard(event_uid):
    db = database.get_db()
    event = g.event
    secret = g.admin_secret

    active_days_config = json.loads(event["active_days"])
    active_days = get_ordered_active_days(active_days_config)

    # Create a dictionary from the database row for the template
    event_dict = {
        "uid": event["uid"],
        "name": event["name"],
        "active_days": active_days_config,
        "server_id": event["server_id"],
    }

    # 1. Group submissions by day_type
    submissions_raw = db.execute(
        "SELECT * FROM submissions WHERE event_uid = ? ORDER BY resources DESC",
        (event_uid,),
    ).fetchall()
    submissions_by_day = {day: [] for day in active_days}
    for row in submissions_raw:
        if row["day_type"] in submissions_by_day:
            sub_dict = dict(row)
            sub_dict["raw_resources"] = parse_json_dict(row["raw_data"])
            submissions_by_day[row["day_type"]].append(sub_dict)

    # 2. Group assignments and related data by day_type
    assignments_raw = db.execute(
        "SELECT * FROM assignments WHERE event_uid = ?", (event_uid,)
    ).fetchall()
    rich_assignments = {day: {} for day in active_days}
    assignments_by_sub_id = {}
    submissions_map = {
        (sub["day_type"], sub["player_id"]): sub for sub in submissions_raw
    }

    for a in assignments_raw:
        day_type = a["day_type"]
        player_id = a["player_id"]
        if day_type in rich_assignments:
            submission = submissions_map.get((day_type, player_id))
            if submission:
                rich_assignments[day_type][a["slot_index"]] = {
                    "player_id": player_id,
                    "player_name": submission["player_name"],
                    "alliance_name": submission["alliance_name"],
                    "avatar_url": submission["avatar_url"],
                    "is_locked": a["is_locked"],
                }
        assignments_by_sub_id[(a["day_type"], a["player_id"])] = a

    # 3. Group everything else by day_type
    slot_count = event["slot_count"] if event["slot_count"] is not None else 49
    slot_density = {day: [0] * slot_count for day in active_days}
    slot_players = {day: {i: [] for i in range(slot_count)} for day in active_days}
    max_density = {day: 1 for day in active_days}
    available_slots = {day: [] for day in active_days}

    slot_labels = generate_slot_labels(slot_count)

    for day in active_days:
        # Heatmap & Requested Slots Text
        for sub in submissions_by_day[day]:
            if not sub["feasible_slots"]:
                sub["requested_slots_text"] = "No slots selected"
                sub["requested_slots_labels"] = []
            else:
                try:
                    feasible_slots = json.loads(sub["feasible_slots"])
                    requested_labels = [
                        slot_labels[i]
                        for i in feasible_slots
                        if isinstance(i, int) and 0 <= i < slot_count
                    ]
                    sub["requested_slots_labels"] = requested_labels
                    sub["requested_slots_text"] = (
                        ", ".join(requested_labels)
                        if requested_labels
                        else "No slots selected"
                    )

                    for slot_index in feasible_slots:
                        if isinstance(slot_index, int) and 0 <= slot_index < slot_count:
                            slot_density[day][slot_index] += 1
                            slot_players[day][slot_index].append(
                                {
                                    "player_name": sub["player_name"],
                                    "alliance_name": sub["alliance_name"],
                                    "resources": sub["resources"],
                                    "submission_id": sub["id"],
                                }
                            )
                except (json.JSONDecodeError, TypeError, KeyError):
                    sub["requested_slots_text"] = "Error parsing slots"
                    sub["requested_slots_labels"] = []

            # Resources Hover Text
            try:
                raw_resources = json.loads(sub["raw_data"])
                parts = []
                if day == "construction":
                    if raw_resources.get("speedups"):
                        parts.append(
                            f"Speedups: {format_minutes(raw_resources['speedups'])}"
                        )
                    if raw_resources.get("truegold"):
                        parts.append(f"Truegold: {raw_resources['truegold']}")
                    if raw_resources.get("tempered_truegold"):
                        parts.append(
                            f"Tempered Gold: {raw_resources['tempered_truegold']}"
                        )
                elif day == "training":
                    if raw_resources.get("speedups"):
                        parts.append(
                            f"Speedups: {format_minutes(raw_resources['speedups'])}"
                        )
                elif day == "research":
                    if raw_resources.get("speedups"):
                        parts.append(
                            f"Speedups: {format_minutes(raw_resources['speedups'])}"
                        )
                    if raw_resources.get("truegold_dust"):
                        parts.append(f"Dust: {raw_resources['truegold_dust']}")
                sub["resources_text"] = " | ".join(parts) if parts else "No raw data"
            except (json.JSONDecodeError, TypeError):
                sub["resources_text"] = "Error parsing resources"

        max_density[day] = max(slot_density[day]) if any(slot_density[day]) else 1

        # Available Slots
        assigned_slots_for_day = rich_assignments[day].keys()
        available_slots[day] = [
            i for i in range(slot_count) if i not in assigned_slots_for_day
        ]

    # Generate URLs for the admin dashboard links
    player_url = url_for("public.player_form", event_uid=event_uid, _external=True)
    finalized_url = url_for(
        "public.locked_appointments", event_uid=event_uid, _external=True
    )

    insights = compute_event_insights(event_uid, db)

    return render_template(
        "admin_dashboard.html",
        event=event_dict,
        active_days=active_days,
        submissions_by_day=submissions_by_day,
        assignments=rich_assignments,
        assignments_by_sub_id=assignments_by_sub_id,
        available_slots=available_slots,
        secret=secret,
        slot_density=slot_density,
        slot_players=slot_players,
        max_density=max_density,
        player_url=player_url,
        finalized_url=finalized_url,
        insights=insights,
    )


@admin_bp.route("/<event_uid>/manual_assign", methods=["POST"])
@require_admin
def manual_assign(event_uid):
    db = database.get_db()
    event = g.event
    secret = g.admin_secret

    submission_id = request.form.get("submission_id")
    slot_index = request.form.get("slot_index")

    if not slot_index:  # Don't do anything if the slot is empty
        return redirect(
            url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
        )

    try:
        slot_idx_val = int(slot_index)
        slot_count = event["slot_count"] if event["slot_count"] is not None else 49
        if not (0 <= slot_idx_val < slot_count):
            return "Invalid slot index range", 400
    except (ValueError, TypeError):
        return "Invalid slot index format", 400

    if not submission_id:
        return "Missing submission_id", 400
    try:
        _, player_id, day_type = submission_id.split("_", 2)
    except (ValueError, AttributeError):
        return "Invalid submission_id format", 400

    sub = db.execute(
        "SELECT 1 FROM submissions WHERE id = ? AND event_uid = ?",
        (submission_id, event_uid),
    ).fetchone()
    if not sub:
        return "Submission not found", 404

    audit_logger.info(
        f"ADMIN: Manual assign - Player {player_id} to slot {slot_idx_val} for day {day_type} in event {event_uid}"
    )

    # Check if there is an existing assignment in this slot that will be overridden
    existing_assignment = db.execute(
        "SELECT player_id FROM assignments WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
        (event_uid, day_type, slot_idx_val),
    ).fetchone()
    if existing_assignment and existing_assignment["player_id"] != player_id:
        db.execute(
            "UPDATE submissions SET status = 'Pending' WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, existing_assignment["player_id"], day_type),
        )

    # Delete any pre-existing assignment for this player on this day
    db.execute(
        "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
        (event_uid, player_id, day_type),
    )

    # Overwrite whatever was in the target slot and lock it
    db.execute(
        "REPLACE INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        (event_uid, day_type, slot_idx_val, player_id, 1),
    )

    # Update submission status to 'Locked'
    db.execute(
        "UPDATE submissions SET status = 'Locked' WHERE event_uid = ? AND player_id = ? AND day_type = ?",
        (event_uid, player_id, day_type),
    )

    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/distribute", methods=["POST"])
@require_admin
def distribute(event_uid):
    secret = g.admin_secret

    day_type = request.form.get("day_type")
    audit_logger.info(
        f"ADMIN: Automatic distribution triggered for event {event_uid}, day {day_type or 'all'}"
    )
    logic.run_distribution_algorithm(event_uid, day_type)

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/export/<day_type>", methods=["GET"])
@require_admin
def export_csv(event_uid, day_type):
    db = database.get_db()
    event = g.event

    # Fetch locked assignments joined with submissions to get player name
    assignments = db.execute(
        """
        SELECT a.day_type, a.player_id, s.player_name, a.slot_index
        FROM assignments a
        JOIN submissions s ON a.event_uid = s.event_uid AND a.day_type = s.day_type AND a.player_id = s.player_id
        WHERE a.event_uid = ? AND a.day_type = ? AND a.is_locked = 1
        ORDER BY a.slot_index ASC
        """,
        (event_uid, day_type),
    ).fetchall()

    slot_count = event["slot_count"] if event["slot_count"] is not None else 49
    slot_labels = generate_slot_labels(slot_count)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event Type", "Player ID", "Player Name", "Appointment Slot"])
    for a in assignments:
        slot_idx = a["slot_index"]
        slot_lbl = (
            slot_labels[slot_idx]
            if slot_idx is not None and 0 <= slot_idx < len(slot_labels)
            else ""
        )
        writer.writerow([a["day_type"], a["player_id"], a["player_name"], slot_lbl])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=schedule_{event['uid']}_{day_type}.csv"
        },
    )


@admin_bp.route("/<event_uid>/export_submissions", methods=["GET"])
@require_admin
def export_submissions(event_uid):
    db = database.get_db()

    submissions = db.execute(
        """
        SELECT day_type, player_name, player_id, avatar_url, backpack_url, 
               alliance_name, resources, raw_data, feasible_slots, status 
        FROM submissions 
        WHERE event_uid = ?
        """,
        (event_uid,),
    ).fetchall()

    sub_list = []
    for s in submissions:
        sub_list.append(
            {
                "day_type": s["day_type"],
                "player_name": s["player_name"],
                "player_id": s["player_id"],
                "avatar_url": s["avatar_url"],
                "backpack_url": s["backpack_url"],
                "alliance_name": s["alliance_name"],
                "resources": s["resources"],
                "raw_data": s["raw_data"],
                "feasible_slots": s["feasible_slots"],
                "status": s["status"],
            }
        )

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"submissions_{event_uid}_{timestamp}.json"

    return Response(
        json.dumps(sub_list, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route("/<event_uid>/import_submissions", methods=["POST"])
@require_admin
def import_submissions(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    file = request.files.get("submissions_file")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return redirect(
            url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
        )

    try:
        data = json.load(file)
    except Exception:  # noqa: BLE001
        flash("Invalid file format. Please upload a valid JSON file.", "error")
        return redirect(
            url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
        )

    if not isinstance(data, list):
        flash(
            "Invalid JSON schema. Submissions must be formatted as an array.",
            "error",
        )
        return redirect(
            url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
        )

    required_fields = [
        "day_type",
        "player_name",
        "player_id",
        "resources",
        "raw_data",
        "feasible_slots",
    ]
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            flash(f"Item at index {idx} is not a valid submission object.", "error")
            return redirect(
                url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
            )
        for field in required_fields:
            if field not in item:
                flash(
                    f"Missing required field '{field}' at submission index {idx}.",
                    "error",
                )
                return redirect(
                    url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
                )

        # Validate resources can be parsed to float, convert and save as float
        try:
            item["resources"] = float(item["resources"])
        except (ValueError, TypeError):
            flash("Must be a number.", "error")
            return redirect(
                url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
            )

        # Validate and normalize feasible_slots to JSON string of list of integers
        fs_val = item["feasible_slots"]
        if isinstance(fs_val, str):
            try:
                fs_val = json.loads(fs_val)
            except Exception:  # noqa: BLE001
                flash("feasible_slots must be a list.", "error")
                return redirect(
                    url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
                )
        if not isinstance(fs_val, list):
            flash("feasible_slots must be a list.", "error")
            return redirect(
                url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
            )
        try:
            fs_val = [int(x) for x in fs_val]
        except (ValueError, TypeError):
            flash("feasible_slots must be a list of integers.", "error")
            return redirect(
                url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
            )
        item["feasible_slots"] = json.dumps(fs_val)

        # Validate and normalize raw_data to JSON string of a dictionary/object
        rd_val = item["raw_data"]
        if isinstance(rd_val, str):
            try:
                rd_val = json.loads(rd_val)
            except Exception:  # noqa: BLE001
                flash("raw_data must be a JSON object.", "error")
                return redirect(
                    url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
                )
        if not isinstance(rd_val, dict):
            flash("raw_data must be a JSON object.", "error")
            return redirect(
                url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
            )
        item["raw_data"] = json.dumps(rd_val)

    # Process upserts inside transaction
    unique_players = list({item["player_id"] for item in data})

    # Delete existing matching records (for the specific player_id and day_type)
    for item in data:
        db.execute(
            "DELETE FROM submissions WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, item["player_id"], item["day_type"]),
        )
        db.execute(
            "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, item["player_id"], item["day_type"]),
        )

    # Insert the imported submissions
    for item in data:
        sub_id = f"{event_uid}_{item['player_id']}_{item['day_type']}"
        raw_data_str = (
            item["raw_data"]
            if isinstance(item["raw_data"], str)
            else json.dumps(item["raw_data"])
        )
        feasible_slots_str = (
            item["feasible_slots"]
            if isinstance(item["feasible_slots"], str)
            else json.dumps(item["feasible_slots"])
        )

        db.execute(
            """
            INSERT INTO submissions (
                id, event_uid, day_type, player_name, player_id, 
                avatar_url, backpack_url, alliance_name, resources, 
                raw_data, feasible_slots, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sub_id,
                event_uid,
                item["day_type"],
                item["player_name"],
                item["player_id"],
                validate_safe_url(item.get("avatar_url")),
                validate_safe_url(item.get("backpack_url")),
                item.get("alliance_name"),
                item["resources"],
                raw_data_str,
                feasible_slots_str,
                item.get("status", "Pending"),
            ),
        )

    db.commit()
    audit_logger.info(
        f"ADMIN: Imported {len(data)} submissions for {len(unique_players)} players in event {event_uid}"
    )
    flash(
        f"Successfully imported {len(data)} submissions for {len(unique_players)} players.",
        "success",
    )

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/refresh_players", methods=["POST"])
@require_admin
def refresh_players(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    audit_logger.info(f"ADMIN: Refresh player data triggered for event {event_uid}")

    players = db.execute(
        "SELECT DISTINCT player_id FROM submissions WHERE event_uid = ?",
        (event_uid,),
    ).fetchall()

    refreshed_count = 0
    for p in players:
        fid = p["player_id"]
        info = app.fetch_player_info(fid)
        if info and info.get("nickname"):
            db.execute(
                "UPDATE submissions SET player_name = ?, avatar_url = ? WHERE event_uid = ? AND player_id = ?",
                (info["nickname"], info.get("avatar_url"), event_uid, fid),
            )
            refreshed_count += 1

    db.commit()
    flash(
        f"Refreshed player details for {refreshed_count} player(s).",
        "success",
    )
    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/confirm", methods=["POST"])
@require_admin
def confirm(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    slot_index = request.form.get("slot_index")
    day_type = request.form.get("day_type")

    # Get the player_id for this assignment
    assignment = db.execute(
        "SELECT player_id FROM assignments WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
        (event_uid, day_type, slot_index),
    ).fetchone()

    db.execute(
        "UPDATE assignments SET is_locked = 1 WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
        (event_uid, day_type, slot_index),
    )

    audit_logger.info(
        f"ADMIN: Lock - Slot {slot_index} for day {day_type} in event {event_uid}"
    )

    if assignment:
        db.execute(
            "UPDATE submissions SET status = 'Locked' WHERE event_uid = ? AND day_type = ? AND player_id = ?",
            (event_uid, day_type, assignment["player_id"]),
        )

    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/unlock", methods=["POST"])
@require_admin
def unlock(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    slot_index = request.form.get("slot_index")
    day_type = request.form.get("day_type")

    # Get the player_id for this assignment
    assignment = db.execute(
        "SELECT player_id FROM assignments WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
        (event_uid, day_type, slot_index),
    ).fetchone()

    db.execute(
        "UPDATE assignments SET is_locked = 0 WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
        (event_uid, day_type, slot_index),
    )

    audit_logger.info(
        f"ADMIN: Unlock - Slot {slot_index} for day {day_type} in event {event_uid}"
    )

    if assignment:
        db.execute(
            "UPDATE submissions SET status = 'Confirmed' WHERE event_uid = ? AND day_type = ? AND player_id = ?",
            (event_uid, day_type, assignment["player_id"]),
        )

    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/delete", methods=["POST"])
@require_admin
def delete(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    submission_id = request.form.get("submission_id")

    audit_logger.info(f"ADMIN: Delete submission {submission_id} in event {event_uid}")

    # Find player_id and day_type from submission_id
    _, player_id, day_type = submission_id.split("_", 2)

    # First, clear the specific assignment for this player and day
    db.execute(
        "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
        (event_uid, player_id, day_type),
    )

    # Then, delete the submission
    db.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))

    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/update_alliance", methods=["POST"])
@require_admin
def update_alliance(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    submission_id = request.form.get("submission_id")
    new_alliance_name = request.form.get("alliance_name").strip()

    audit_logger.info(
        f"ADMIN: Update alliance for submission {submission_id} to {new_alliance_name} in event {event_uid}"
    )

    db.execute(
        "UPDATE submissions SET alliance_name = ? WHERE id = ? AND event_uid = ?",
        (new_alliance_name, submission_id, event_uid),
    )
    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/override_resources", methods=["POST"])
@require_admin
def override_resources(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    submission_id = request.form.get("submission_id")
    submission = db.execute(
        "SELECT * FROM submissions WHERE id = ? AND event_uid = ?",
        (submission_id, event_uid),
    ).fetchone()

    if submission is None:
        return "Submission not found", 404

    day_type = submission["day_type"]

    try:
        if day_type == "construction":
            speedups = int(request.form.get("speedups") or 0)
            truegold = int(request.form.get("truegold") or 0)
            tempered_truegold = int(request.form.get("tempered_truegold") or 0)
            raw_data = {
                "speedups": speedups,
                "truegold": truegold,
                "tempered_truegold": tempered_truegold,
            }
            score = compute_score(day_type, raw_data)
        elif day_type == "training":
            speedups = int(request.form.get("speedups") or 0)
            raw_data = {"speedups": speedups}
            score = compute_score(day_type, raw_data)
        elif day_type == "research":
            speedups = int(request.form.get("speedups") or 0)
            truegold_dust = int(request.form.get("truegold_dust") or 0)
            raw_data = {"speedups": speedups, "truegold_dust": truegold_dust}
            score = compute_score(day_type, raw_data)
        else:
            return "Invalid day type", 400
    except ValueError:
        return "Invalid resource values", 400

    audit_logger.info(
        f"ADMIN: Override resources for submission {submission_id} (day_type={day_type}) - score={score}, raw_data={raw_data} in event {event_uid}"
    )

    db.execute(
        "UPDATE submissions SET resources = ?, raw_data = ? WHERE id = ? AND event_uid = ?",
        (score, json.dumps(raw_data), submission_id, event_uid),
    )
    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/unset", methods=["POST"])
@require_admin
def unset_assignment(event_uid):
    db = database.get_db()
    secret = g.admin_secret

    submission_id = request.form.get("submission_id")
    if not submission_id:
        return "Missing submission_id", 400
    try:
        _, player_id, day_type = submission_id.split("_", 2)
    except (ValueError, AttributeError):
        return "Invalid submission_id format", 400

    audit_logger.info(
        f"ADMIN: Unset assignment for Player {player_id} on day {day_type} in event {event_uid}"
    )

    # Delete the assignment for this player on this day
    db.execute(
        "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
        (event_uid, player_id, day_type),
    )

    # Update submission status back to 'Pending'
    db.execute(
        "UPDATE submissions SET status = 'Pending' WHERE event_uid = ? AND player_id = ? AND day_type = ?",
        (event_uid, player_id, day_type),
    )

    db.commit()

    return redirect(
        url_for("admin.admin_dashboard", event_uid=event_uid, secret=secret)
    )


@admin_bp.route("/<event_uid>/logs")
@require_admin
def view_logs(event_uid):
    log_path = os.path.join(current_app.root_path, "..", "logs", "audit.log")
    if not os.path.exists(log_path):
        return "Log file not found", 404

    with open(log_path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        # Filter lines specifically for this event_uid to enforce tenant isolation
        matching_lines = [line for line in all_lines if event_uid in line][-1000:]
        content = "".join(matching_lines)

    return Response(content, mimetype="text/plain")
