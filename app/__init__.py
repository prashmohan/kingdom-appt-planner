import uuid
import json
import sqlite3
import hashlib
import time
import os
import requests
import mimetypes
import markdown
import csv
import io
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, g, jsonify, Response
from . import database, logic
from config import Config

# Ensure .js files are served with the correct MIME type
mimetypes.add_type("application/javascript", ".js")


def generate_slot_labels():
    labels = []
    for i in range(49):
        # Total minutes from midnight for the start of the slot
        # Slot 0 starts at T-15m (23:45)
        start_total_minutes = (i * 30) - 15

        # Handle negative minutes for slot 0 by wrapping around
        if start_total_minutes < 0:
            start_total_minutes += 24 * 60

        start_hour = start_total_minutes // 60
        start_min = start_total_minutes % 60

        # End time is 30 minutes after start time
        end_total_minutes = start_total_minutes + 30

        # Handle wrap around for end time
        end_hour = (end_total_minutes // 60) % 24
        end_min = end_total_minutes % 60

        labels.append(f"{start_hour:02d}:{start_min:02d}-\u200b{end_hour:02d}:{end_min:02d}")
    return labels


def fetch_player_info(fid):
    # Generate Signature based on analyzed code
    t = int(time.time() * 1000)
    secret = "mN4!pQs6JrYwV9"
    sign_str = f"fid={fid}&time={t}{secret}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    try:
        resp = requests.post(
            "https://kingshot-giftcode.centurygame.com/api/player",
            data={"fid": fid, "time": t, "sign": sign},
            timeout=5,
        )
        data = resp.json()

        # The API returns success when "code" is 0
        if data.get("code") == 0:
            inner_data = data.get("data", {})
            return {
                "nickname": inner_data.get("nickname"),
                "avatar_url": inner_data.get("avatar_image"),
            }
    except Exception:
        pass
    return None


def create_app():
    app = Flask(__name__)
    database.init_app(app)

    # Make the label generator available to all templates
    @app.context_processor
    def inject_global_config():
        return dict(
            slot_labels=generate_slot_labels(),
            enable_screenshot_upload=Config.ENABLE_SCREENSHOT_UPLOAD
        )

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/guide")
    def guide():
        try:
            with open("README.md", "r", encoding="utf-8") as f:
                content = f.read()
            html_content = markdown.markdown(content, extensions=["extra", "toc"])
            return render_template("guide.html", content=html_content)
        except FileNotFoundError:
            return "Guide not found", 404

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    @app.route("/api/proxy/player", methods=["POST"])
    def proxy_player():
        fid = request.json.get("fid")
        if not fid:
            return jsonify({"error": "Missing fid"}), 400

        player_info = fetch_player_info(fid)

        if player_info:
            return jsonify(player_info)
        else:
            return jsonify({"error": "Player not found or API error"}), 404

    @app.route("/admin/<event_uid>/refresh_players", methods=["POST"])
    def refresh_players(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        # Get all unique player IDs for this event
        players = db.execute(
            "SELECT DISTINCT player_id FROM submissions WHERE event_uid = ?",
            (event_uid,),
        ).fetchall()

        for p in players:
            fid = p["player_id"]
            info = fetch_player_info(fid)
            if info:
                db.execute(
                    "UPDATE submissions SET player_name = ?, avatar_url = ? WHERE event_uid = ? AND player_id = ?",
                    (info["nickname"], info["avatar_url"], event_uid, fid),
                )

        db.commit()
        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/create", methods=["POST"])
    def create_event():
        event_name = request.form["event_name"]

        # All events will now have all 3 days active by default.
        active_days = {"construction": True, "training": True, "research": True}

        uid = str(uuid.uuid4())
        admin_secret = str(uuid.uuid4())

        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (uid, event_name, json.dumps(active_days), admin_secret),
        )
        db.commit()

        return redirect(url_for("success", event_uid=uid, secret=admin_secret))

    @app.route("/success/<event_uid>")
    def success(event_uid):
        secret = request.args.get("secret")

        player_url = url_for("player_form", event_uid=event_uid, _external=True)
        admin_url = url_for(
            "admin_dashboard", event_uid=event_uid, secret=secret, _external=True
        )
        finalized_url = url_for(
            "locked_appointments", event_uid=event_uid, _external=True
        )

        return render_template(
            "success.html",
            player_url=player_url,
            admin_url=admin_url,
            finalized_url=finalized_url,
        )

    @app.route("/event/<event_uid>/finalized")
    def locked_appointments(event_uid):
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()

        if event is None:
            return "Event not found", 404

        active_days = [
            day
            for day, is_active in json.loads(event["active_days"]).items()
            if is_active
        ]

        # Fetch only locked assignments
        assignments_raw = db.execute(
            "SELECT * FROM assignments WHERE event_uid = ? AND is_locked = 1",
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
        locked_assignments = {day: {} for day in active_days}
        for a in assignments_raw:
            day_type = a["day_type"]
            player_id = a["player_id"]
            if day_type in locked_assignments:
                submission = submissions_map.get((day_type, player_id))
                if submission:
                    locked_assignments[day_type][a["slot_index"]] = {
                        "player_id": player_id,
                        "player_name": submission["player_name"],
                        "alliance_name": submission["alliance_name"],
                        "avatar_url": submission["avatar_url"],
                    }

        return render_template(
            "locked_appointments.html",
            event=event,
            active_days=active_days,
            assignments=locked_assignments,
        )

    @app.route("/event/<event_uid>")
    def player_form(event_uid):
        db = database.get_db()
        # Use a dictionary cursor for easier row access
        db.row_factory = sqlite3.Row
        event_cursor = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,))
        event = event_cursor.fetchone()

        if event is None:
            return "Event not found", 404

        # Create a dictionary from the database row
        event_dict = {
            "uid": event["uid"],
            "name": event["name"],
            "active_days": json.loads(event["active_days"]),
        }

        return render_template("player_form.html", event=event_dict)

    @app.route("/event/<event_uid>/submit", methods=["POST"])
    def submit(event_uid):
        db = database.get_db()
        player_id = request.form["player_id"].strip().lower()
        player_name = request.form.get("player_name", "").strip()

        # Server-side validation
        if not player_id.isdigit():
            return "Invalid Player ID: Must be numeric", 400
        
        if not player_name:
            return "Invalid Player ID: Could not resolve to a name", 400

        # Handle backpack screenshot upload
        backpack_url = None
        if Config.ENABLE_SCREENSHOT_UPLOAD and "backpack_screenshot" in request.files:
            file = request.files["backpack_screenshot"]
            if file and file.filename:
                # Create upload directory if it doesn't exist
                upload_dir = os.path.join(app.static_folder, "uploads")
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir)
                
                # Generate unique filename: event_uid + player_id + timestamp + original filename
                filename = secure_filename(f"{event_uid}_{player_id}_{int(time.time())}_{file.filename}")
                file.save(os.path.join(upload_dir, filename))
                backpack_url = url_for("static", filename=f"uploads/{filename}")

        # First, delete all previous submissions for this player and event.
        db.execute(
            "DELETE FROM submissions WHERE event_uid = ? AND player_id = ?",
            (event_uid, player_id),
        )

        # Then, insert the new submissions from the form.
        player_name = request.form["player_name"]
        alliance_name = request.form["alliance_name"]
        avatar_url = request.form.get("avatar_url")

        # --- Process Construction Submission ---
        construction_speedups = int(request.form.get("speedups-construction") or 0)
        truegold = int(request.form.get("truegold") or 0)
        feasible_slots = request.form.get("slots-construction", "[]")
        if (construction_speedups > 0 or truegold > 0) and feasible_slots != "[]":
            day_type = "construction"
            score = (construction_speedups * 30) + (truegold * 2000)
            raw_data = {"speedups": construction_speedups, "truegold": truegold}
            submission_id = f"{event_uid}_{player_id}_{day_type}"
            db.execute(
                "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, avatar_url, backpack_url, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    submission_id,
                    event_uid,
                    day_type,
                    player_name,
                    player_id,
                    avatar_url,
                    backpack_url,
                    alliance_name,
                    score,
                    json.dumps(raw_data),
                    feasible_slots,
                ),
            )

        # --- Process Training Submission ---
        training_speedups = int(request.form.get("speedups-training") or 0)
        feasible_slots = request.form.get("slots-training", "[]")
        if training_speedups > 0 and feasible_slots != "[]":
            day_type = "training"
            score = training_speedups * 90
            raw_data = {"speedups": training_speedups}
            submission_id = f"{event_uid}_{player_id}_{day_type}"
            db.execute(
                "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, avatar_url, backpack_url, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    submission_id,
                    event_uid,
                    day_type,
                    player_name,
                    player_id,
                    avatar_url,
                    backpack_url,
                    alliance_name,
                    score,
                    json.dumps(raw_data),
                    feasible_slots,
                ),
            )

        # --- Process Research Submission ---
        research_speedups = int(request.form.get("speedups-research") or 0)
        truegold_dust = int(request.form.get("truegold_dust") or 0)
        feasible_slots = request.form.get("slots-research", "[]")
        if (research_speedups > 0 or truegold_dust > 0) and feasible_slots != "[]":
            day_type = "research"
            score = (research_speedups * 30) + (truegold_dust * 1000)
            raw_data = {"speedups": research_speedups, "truegold_dust": truegold_dust}
            submission_id = f"{event_uid}_{player_id}_{day_type}"
            db.execute(
                "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, avatar_url, backpack_url, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    submission_id,
                    event_uid,
                    day_type,
                    player_name,
                    player_id,
                    avatar_url,
                    backpack_url,
                    alliance_name,
                    score,
                    json.dumps(raw_data),
                    feasible_slots,
                ),
            )

        db.commit()

        return redirect(url_for("submission_success"))

    @app.route("/submission-success")
    def submission_success():
        return render_template("submission_success.html")

    @app.route("/admin/<event_uid>")
    def admin_dashboard(event_uid):
        db = database.get_db()
        db.row_factory = sqlite3.Row

        secret = request.args.get("secret")
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()

        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        active_days = [
            day
            for day, is_active in json.loads(event["active_days"]).items()
            if is_active
        ]

        # 1. Group submissions by day_type
        submissions_raw = db.execute(
            "SELECT * FROM submissions WHERE event_uid = ? ORDER BY resources DESC",
            (event_uid,),
        ).fetchall()
        submissions_by_day = {day: [] for day in active_days}
        for row in submissions_raw:
            if row["day_type"] in submissions_by_day:
                # Convert sqlite3.Row to a dictionary to allow item assignment
                sub_dict = dict(row)
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
        slot_density = {day: [0] * 49 for day in active_days}
        max_density = {day: 1 for day in active_days}
        available_slots = {day: [] for day in active_days}
        alliance_summary = {day: {} for day in active_days}

        slot_labels = generate_slot_labels()

        for day in active_days:
            # Heatmap & Requested Slots Text
            for sub in submissions_by_day[day]:
                if not sub["feasible_slots"]:
                    sub["requested_slots_text"] = "No slots selected"
                    continue
                try:
                    feasible_slots = json.loads(sub["feasible_slots"])
                    # Create human readable labels for hover text
                    requested_labels = [
                        slot_labels[i] for i in feasible_slots if 0 <= i < 49
                    ]
                    sub["requested_slots_text"] = (
                        ", ".join(requested_labels)
                        if requested_labels
                        else "No slots selected"
                    )

                    for slot_index in feasible_slots:
                        if 0 <= slot_index < 49:
                            slot_density[day][slot_index] += 1

                except (json.JSONDecodeError, TypeError, KeyError):
                    sub["requested_slots_text"] = "Error parsing slots"
                    pass

                # Resources Hover Text
                try:
                    raw_resources = json.loads(sub["raw_data"])
                    parts = []
                    if day == "construction":
                        if raw_resources.get("speedups"):
                            parts.append(f"Speedups: {raw_resources['speedups']}m")
                        if raw_resources.get("truegold"):
                            parts.append(f"Truegold: {raw_resources['truegold']}")
                    elif day == "training":
                        if raw_resources.get("speedups"):
                            parts.append(f"Speedups: {raw_resources['speedups']}m")
                    elif day == "research":
                        if raw_resources.get("speedups"):
                            parts.append(f"Speedups: {raw_resources['speedups']}m")
                        if raw_resources.get("truegold_dust"):
                            parts.append(f"Dust: {raw_resources['truegold_dust']}")
                    sub["resources_text"] = " | ".join(parts) if parts else "No raw data"
                except (json.JSONDecodeError, TypeError):
                    sub["resources_text"] = "Error parsing resources"

            max_density[day] = max(slot_density[day]) if any(slot_density[day]) else 1

            # Available Slots
            assigned_slots_for_day = rich_assignments[day].keys()
            available_slots[day] = [
                i for i in range(49) if i not in assigned_slots_for_day
            ]

            # Alliance Summary
            day_summary = {}
            for sub in submissions_by_day[day]:
                alliance_name = sub["alliance_name"] or "No Alliance"
                if alliance_name not in day_summary:
                    day_summary[alliance_name] = {
                        "total_resources": 0,
                        "submissions_count": 0,
                        "assigned_count": 0,
                    }
                day_summary[alliance_name]["total_resources"] += sub["resources"]
                day_summary[alliance_name]["submissions_count"] += 1

            for assignment in rich_assignments[day].values():
                alliance_name = assignment["alliance_name"] or "No Alliance"
                if alliance_name in day_summary:
                    day_summary[alliance_name]["assigned_count"] += 1
            alliance_summary[day] = day_summary

        # Generate URLs for the admin dashboard links
        player_url = url_for("player_form", event_uid=event_uid, _external=True)
        finalized_url = url_for(
            "locked_appointments", event_uid=event_uid, _external=True
        )

        return render_template(
            "admin_dashboard.html",
            event=event,
            active_days=active_days,
            submissions_by_day=submissions_by_day,
            assignments=rich_assignments,
            assignments_by_sub_id=assignments_by_sub_id,
            available_slots=available_slots,
            secret=secret,
            slot_density=slot_density,
            max_density=max_density,
            alliance_summary=alliance_summary,
            player_url=player_url,
            finalized_url=finalized_url,
        )

    @app.route("/event/<event_uid>/schedule")
    def public_schedule(event_uid):
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()

        if event is None:
            return "Event not found", 404

        active_days = [
            day
            for day, is_active in json.loads(event["active_days"]).items()
            if is_active
        ]
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
            event=event,
            active_days=active_days,
            assignments=assignments,
        )

    @app.route("/admin/<event_uid>/manual_assign", methods=["POST"])
    def manual_assign(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        submission_id = request.form.get("submission_id")
        slot_index = request.form.get("slot_index")

        if not slot_index:  # Don't do anything if the slot is empty
            return redirect(
                url_for("admin_dashboard", event_uid=event_uid, secret=secret)
            )

        _, player_id, day_type = submission_id.split("_", 2)

        # Delete any pre-existing assignment for this player on this day
        db.execute(
            "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, player_id, day_type),
        )

        # Overwrite whatever was in the target slot and lock it
        db.execute(
            "REPLACE INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
            (event_uid, day_type, slot_index, player_id, 1),
        )

        # Update submission status to 'Locked'
        db.execute(
            "UPDATE submissions SET status = 'Locked' WHERE event_uid = ? AND player_id = ? AND day_type = ?", 
            (event_uid, player_id, day_type)
        )

        db.commit()

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/distribute", methods=["POST"])
    def distribute(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        day_type = request.form.get("day_type")
        logic.run_distribution_algorithm(event_uid, day_type)

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/export/<day_type>", methods=["GET"])
    def export_csv(event_uid, day_type):
        secret = request.args.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

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

        slot_labels = generate_slot_labels()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Event Type", "Player ID", "Player Name", "Appointment Slot"])

        for a in assignments:
            writer.writerow(
                [
                    a["day_type"],
                    a["player_id"],
                    a["player_name"],
                    slot_labels[a["slot_index"]],
                ]
            )

        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=schedule_{event['uid']}_{day_type}.csv"
            },
        )

    @app.route("/admin/<event_uid>/confirm", methods=["POST"])
    def confirm(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        slot_index = request.form.get("slot_index")
        day_type = request.form.get("day_type")
        
        # Get the player_id for this assignment
        assignment = db.execute(
            "SELECT player_id FROM assignments WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
            (event_uid, day_type, slot_index)
        ).fetchone()

        db.execute(
            "UPDATE assignments SET is_locked = 1 WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
            (event_uid, day_type, slot_index),
        )
        
        if assignment:
            db.execute(
                "UPDATE submissions SET status = 'Locked' WHERE event_uid = ? AND day_type = ? AND player_id = ?",
                (event_uid, day_type, assignment["player_id"])
            )
            
        db.commit()

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/unlock", methods=["POST"])
    def unlock(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        slot_index = request.form.get("slot_index")
        day_type = request.form.get("day_type")
        
        # Get the player_id for this assignment
        assignment = db.execute(
            "SELECT player_id FROM assignments WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
            (event_uid, day_type, slot_index)
        ).fetchone()

        db.execute(
            "UPDATE assignments SET is_locked = 0 WHERE event_uid = ? AND day_type = ? AND slot_index = ?",
            (event_uid, day_type, slot_index),
        )
        
        if assignment:
            db.execute(
                "UPDATE submissions SET status = 'Confirmed' WHERE event_uid = ? AND day_type = ? AND player_id = ?",
                (event_uid, day_type, assignment["player_id"])
            )
            
        db.commit()

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/delete", methods=["POST"])
    def delete(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        submission_id = request.form.get("submission_id")

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

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/update_alliance", methods=["POST"])
    def update_alliance(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        submission_id = request.form.get("submission_id")
        new_alliance_name = request.form.get("alliance_name").strip()

        db.execute(
            "UPDATE submissions SET alliance_name = ? WHERE id = ? AND event_uid = ?",
            (new_alliance_name, submission_id, event_uid),
        )
        db.commit()

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    @app.route("/admin/<event_uid>/unset", methods=["POST"])
    def unset_assignment(event_uid):
        secret = request.form.get("secret")
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()
        if event is None:
            return "Event not found", 404
        if event["admin_secret"] != secret:
            return "Forbidden", 403

        submission_id = request.form.get("submission_id")
        _, player_id, day_type = submission_id.split("_", 2)

        # Delete the assignment for this player on this day
        db.execute(
            "DELETE FROM assignments WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, player_id, day_type),
        )

        # Update submission status back to 'Pending'
        db.execute(
            "UPDATE submissions SET status = 'Pending' WHERE event_uid = ? AND player_id = ? AND day_type = ?",
            (event_uid, player_id, day_type)
        )

        db.commit()

        return redirect(url_for("admin_dashboard", event_uid=event_uid, secret=secret))

    return app


app = create_app()
