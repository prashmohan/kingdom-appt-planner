import json
import re
import secrets
import sqlite3
import string
from collections import Counter
from typing import Any

from . import database

RESERVED_SLUGS = {
    "admin",
    "create",
    "distribute",
    "event",
    "export_csv",
    "guide",
    "static",
    "success",
    "confirm",
    "unlock",
    "delete",
    "manual_assign",
    "unset",
    "override_resources",
    "update_alliance",
    "submission-success",
    "favicon.ico",
    "superadmin",
}


def generate_short_uid(length: int = 8) -> str:
    """Generate a high-entropy URL-safe alphanumeric ID (Base62)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_custom_slug(
    slug: str, db: sqlite3.Connection | None = None
) -> tuple[bool, str | None]:
    """Validate format, length, reserved keywords, and uniqueness for a custom slug."""
    if not slug or len(slug) < 3 or len(slug) > 32:
        return False, "Custom URL code must be between 3 and 32 characters."

    if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
        return (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )

    if slug.lower() in RESERVED_SLUGS:
        return (
            False,
            f"'{slug}' is a reserved keyword. Please choose a different URL code.",
        )

    if db is not None:
        row = db.execute("SELECT 1 FROM events WHERE uid = ?", (slug,)).fetchone()
        if row:
            return (
                False,
                f"URL code '{slug}' is already taken. Please choose a different one.",
            )

    return True, None


def run_distribution_algorithm(event_uid, day_type=None):
    db = database.get_db()
    db.row_factory = sqlite3.Row

    # Get the active day types for the event
    event = db.execute(
        "SELECT active_days, slot_count FROM events WHERE uid = ?", (event_uid,)
    ).fetchone()
    if not event:
        return

    slot_count = event["slot_count"] if event["slot_count"] is not None else 49

    if day_type:
        active_days = [day_type]
    else:
        active_days = get_ordered_active_days(event["active_days"])

    # Reset all relevant submissions for the event to 'Pending' before starting
    if day_type:
        db.execute(
            "UPDATE submissions SET status = 'Pending' WHERE event_uid = ? AND day_type = ?",
            (event_uid, day_type),
        )
    else:
        db.execute(
            "UPDATE submissions SET status = 'Pending' WHERE event_uid = ?",
            (event_uid,),
        )

    # Loop through each active day and run the distribution for it
    for current_day_type in active_days:
        # 1. Preparation for the current day_type
        # Clear all non-locked assignments for this specific day
        db.execute(
            "DELETE FROM assignments WHERE event_uid = ? AND day_type = ? AND is_locked = 0",
            (event_uid, current_day_type),
        )

        # Fetch submissions specifically for this day_type
        submissions = db.execute(
            "SELECT * FROM submissions WHERE event_uid = ? AND day_type = ? ORDER BY resources DESC, timestamp ASC",
            (event_uid, current_day_type),
        ).fetchall()

        # Fetch locked assignments specifically for this day_type
        locked_assignments_raw = db.execute(
            "SELECT * FROM assignments WHERE event_uid = ? AND day_type = ? AND is_locked = 1",
            (event_uid, current_day_type),
        ).fetchall()

        taken_slots = {a["slot_index"] for a in locked_assignments_raw}
        assigned_player_ids = {a["player_id"] for a in locked_assignments_raw}

        # Update status for players who already have locked assignments
        for pid in assigned_player_ids:
            db.execute(
                "UPDATE submissions SET status = 'Locked' WHERE event_uid = ? AND day_type = ? AND player_id = ?",
                (event_uid, current_day_type, pid),
            )

        # 2. Calculate Demand for each slot (static demand based on all submissions for this day)
        slot_demand = {i: 0 for i in range(slot_count)}
        for sub in submissions:
            try:
                if not sub["feasible_slots"]:
                    continue
                f_slots = json.loads(sub["feasible_slots"])
                for s in f_slots:
                    if 0 <= s < slot_count:
                        slot_demand[s] += 1
            except (json.JSONDecodeError, TypeError):
                continue

        # 3. Ranking & Allocation for the current day_type
        for submission in submissions:
            # Skip if player already has a locked assignment for this day
            if submission["player_id"] in assigned_player_ids:
                continue

            is_assigned = False
            try:
                feasible_slots = json.loads(submission["feasible_slots"])
            except (json.JSONDecodeError, TypeError):
                feasible_slots = None

            if not isinstance(feasible_slots, list) or not feasible_slots:
                db.execute(
                    "UPDATE submissions SET status = 'Waitlisted' WHERE id = ?",
                    (submission["id"],),
                )
                continue

            # Filter out invalid indices or non-integers to avoid KeyError/TypeError
            feasible_slots = [
                s for s in feasible_slots if isinstance(s, int) and 0 <= s < slot_count
            ]

            if not feasible_slots:
                db.execute(
                    "UPDATE submissions SET status = 'Waitlisted' WHERE id = ?",
                    (submission["id"],),
                )
                continue

            # Filter to slots that are not yet taken
            available_feasible = [s for s in feasible_slots if s not in taken_slots]

            if available_feasible:
                # SMARTER LOGIC: Pick the slot with the LEAST overall demand
                # This leaves high-demand slots for players who might ONLY be able to do those slots.
                # Tie-break by slot index.
                best_slot = min(available_feasible, key=lambda s: (slot_demand[s], s))

                # Assign this slot to the player for this specific day
                db.execute(
                    """
                    INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        event_uid,
                        current_day_type,
                        best_slot,
                        submission["player_id"],
                        0,
                    ),
                )

                # Update submission status
                db.execute(
                    "UPDATE submissions SET status = 'Confirmed' WHERE id = ?",
                    (submission["id"],),
                )

                taken_slots.add(best_slot)
                assigned_player_ids.add(submission["player_id"])
                is_assigned = True

            if not is_assigned:
                # Waitlist the player
                db.execute(
                    "UPDATE submissions SET status = 'Waitlisted' WHERE id = ?",
                    (submission["id"],),
                )

    db.commit()


def format_minutes(total_minutes):
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


def get_ordered_active_days(active_days_config):
    """
    Returns active days sorted chronologically by day number.
    Supports active_days_config as a dict, list, or JSON string.
    """
    if isinstance(active_days_config, str):
        try:
            active_days_config = json.loads(active_days_config)
        except (json.JSONDecodeError, TypeError):
            return []

    if isinstance(active_days_config, list):
        return [
            d
            for d in active_days_config
            if d in ("construction", "training", "research")
        ]
    if not isinstance(active_days_config, dict):
        return []

    try:
        research_day_num = int(active_days_config.get("research_day", 5) or 5)
    except (ValueError, TypeError):
        research_day_num = 5

    day_numbers = {
        "construction": 1,
        "training": 4,
        "research": research_day_num,
    }

    active = [
        day
        for day in ["construction", "training", "research"]
        if active_days_config.get(day)
    ]
    return sorted(active, key=lambda d: day_numbers.get(d, 99))


def get_superadmin_metrics(
    db: sqlite3.Connection, time_range: str = "all"
) -> dict[str, Any]:
    """
    Computes global platform KPIs, buff distributions, peak time slots, superlatives,
    and per-event details across registered events scoped to the given time_range ('1w', '2w', '4w', 'all').
    """
    valid_range = time_range if time_range in ("1w", "2w", "4w") else "all"

    time_filters = {
        "1w": "-7 days",
        "2w": "-14 days",
        "4w": "-28 days",
    }

    if valid_range in time_filters:
        query = (
            "SELECT uid, name, active_days, admin_secret, slot_count, created_at "
            f"FROM events WHERE created_at >= datetime('now', '{time_filters[valid_range]}') "
            "ORDER BY created_at DESC"
        )
    else:
        query = (
            "SELECT uid, name, active_days, admin_secret, slot_count, created_at "
            "FROM events ORDER BY created_at DESC"
        )

    cur = db.execute(query)
    cols = [c[0] for c in cur.description] if cur.description else []
    raw_events = cur.fetchall()
    events = [dict(zip(cols, row)) for row in raw_events]

    if not events:
        return {
            "time_range": valid_range,
            "total_events": 0,
            "total_submissions": 0,
            "total_unique_players": 0,
            "total_alliances": 0,
            "total_assigned_slots": 0,
            "total_locked_slots": 0,
            "global_fill_rate": 0.0,
            "global_lock_rate": 0.0,
            "total_resources_pledged": 0.0,
            "avg_submissions_per_event": 0.0,
            "buff_distribution": {
                "construction": {"submissions": 0, "assignments": 0},
                "training": {"submissions": 0, "assignments": 0},
                "research": {"submissions": 0, "assignments": 0},
            },
            "peak_time_slots": [],
            "superlatives": {
                "most_contested": None,
                "top_resources": None,
            },
            "top_events": [],
            "events": [],
        }

    event_uids = [e["uid"] for e in events]
    placeholders = ",".join("?" for _ in event_uids)

    # Fetch submissions for matching events
    sub_cur = db.execute(
        "SELECT id, event_uid, day_type, player_name, player_id, alliance_name, resources, feasible_slots, status, timestamp "
        f"FROM submissions WHERE event_uid IN ({placeholders})",
        event_uids,
    )
    sub_cols = [c[0] for c in sub_cur.description] if sub_cur.description else []
    submissions = [dict(zip(sub_cols, row)) for row in sub_cur.fetchall()]

    # Fetch assignments for matching events
    ass_cur = db.execute(
        "SELECT event_uid, day_type, slot_index, player_id, is_locked "
        f"FROM assignments WHERE event_uid IN ({placeholders})",
        event_uids,
    )
    ass_cols = [c[0] for c in ass_cur.description] if ass_cur.description else []
    assignments = [dict(zip(ass_cols, row)) for row in ass_cur.fetchall()]

    total_events = len(events)
    total_submissions = len(submissions)
    total_unique_players = len(
        {s["player_id"] for s in submissions if s.get("player_id")}
    )
    total_alliances = len(
        {
            str(s["alliance_name"]).strip()
            for s in submissions
            if s.get("alliance_name") and str(s.get("alliance_name")).strip()
        }
    )
    total_assigned_slots = len(assignments)
    total_locked_slots = sum(1 for a in assignments if a.get("is_locked"))

    total_capacity = 0
    events_data = []

    # Map submissions and assignments by event_uid for fast aggregation
    subs_by_event: dict[str, list[dict]] = {uid: [] for uid in event_uids}
    for s in submissions:
        subs_by_event.setdefault(s["event_uid"], []).append(s)

    asses_by_event: dict[str, list[dict]] = {uid: [] for uid in event_uids}
    for a in assignments:
        asses_by_event.setdefault(a["event_uid"], []).append(a)

    for e in events:
        uid = e["uid"]
        name = e["name"]
        created_at = str(e["created_at"]) if e.get("created_at") else ""
        active_days_list = get_ordered_active_days(e.get("active_days"))
        sc = e.get("slot_count") if e.get("slot_count") is not None else 49
        admin_secret = e.get("admin_secret", "")

        event_subs = subs_by_event.get(uid, [])
        event_asses = asses_by_event.get(uid, [])

        sub_count = len(event_subs)
        unique_players = len({s["player_id"] for s in event_subs if s.get("player_id")})
        total_event_resources = sum(
            float(s["resources"] or 0.0)
            for s in event_subs
            if s.get("resources") is not None
        )

        assigned_count = len(event_asses)
        locked_count = sum(1 for a in event_asses if a.get("is_locked"))

        event_capacity = sc * len(active_days_list)
        total_capacity += event_capacity

        fill_percentage = (
            round((assigned_count / event_capacity) * 100, 1)
            if event_capacity > 0
            else 0.0
        )
        contest_ratio = (sub_count / event_capacity) if event_capacity > 0 else 0.0

        event_dict = {
            "uid": uid,
            "name": name,
            "created_at": created_at,
            "active_days": active_days_list,
            "slot_count": sc,
            "admin_secret": admin_secret,
            "admin_url": f"/admin/{uid}?secret={admin_secret}",
            "public_url": f"/event/{uid}/schedule",
            "player_url": f"/event/{uid}",
            "submission_count": sub_count,
            "unique_player_count": unique_players,
            "assigned_slot_count": assigned_count,
            "locked_slot_count": locked_count,
            "fill_percentage": fill_percentage,
            "total_resources": total_event_resources,
            "capacity": event_capacity,
            "contest_ratio": contest_ratio,
        }
        events_data.append(event_dict)

    global_fill_rate = (
        round((total_assigned_slots / total_capacity) * 100, 1)
        if total_capacity > 0
        else 0.0
    )
    global_lock_rate = (
        round((total_locked_slots / total_assigned_slots) * 100, 1)
        if total_assigned_slots > 0
        else 0.0
    )
    total_resources_pledged = sum(
        float(s["resources"] or 0.0)
        for s in submissions
        if s.get("resources") is not None
    )
    avg_submissions_per_event = (
        round(total_submissions / total_events, 1) if total_events > 0 else 0.0
    )

    buff_distribution = {
        "construction": {"submissions": 0, "assignments": 0},
        "training": {"submissions": 0, "assignments": 0},
        "research": {"submissions": 0, "assignments": 0},
    }
    for s in submissions:
        day = s.get("day_type")
        if day in buff_distribution:
            buff_distribution[day]["submissions"] += 1

    for a in assignments:
        day = a.get("day_type")
        if day in buff_distribution:
            buff_distribution[day]["assignments"] += 1

    # Peak Time Slots
    slot_counts: Counter[int] = Counter()
    for s in submissions:
        feasible_slots_raw = s.get("feasible_slots")
        if not feasible_slots_raw:
            continue
        try:
            if isinstance(feasible_slots_raw, str):
                f_slots = json.loads(feasible_slots_raw)
            elif isinstance(feasible_slots_raw, list):
                f_slots = feasible_slots_raw
            else:
                f_slots = []
        except (json.JSONDecodeError, TypeError):
            f_slots = []

        if isinstance(f_slots, list):
            for slot_idx in f_slots:
                if isinstance(slot_idx, int) and slot_idx >= 0:
                    slot_counts[slot_idx] += 1

    peak_time_slots = []
    for slot_idx, count in slot_counts.most_common(3):
        start_min = slot_idx * 30
        start_h = (start_min // 60) % 24
        start_m = start_min % 60
        end_min = start_min + 30
        end_h = (end_min // 60) % 24
        end_m = end_min % 60
        slot_label = f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d} UTC"
        peak_time_slots.append(
            {
                "slot": slot_label,
                "slot_index": slot_idx,
                "count": count,
            }
        )

    # Superlatives
    superlatives = {
        "most_contested": None,
        "top_resources": None,
    }
    if events_data:
        most_contested_event = max(
            events_data, key=lambda ev: (ev["contest_ratio"], ev["submission_count"])
        )
        top_res_event = max(
            events_data, key=lambda ev: (ev["total_resources"], ev["submission_count"])
        )
        superlatives["most_contested"] = {
            "uid": most_contested_event["uid"],
            "name": most_contested_event["name"],
            "ratio": round(most_contested_event["contest_ratio"], 2),
            "submission_count": most_contested_event["submission_count"],
            "capacity": most_contested_event["capacity"],
        }
        superlatives["top_resources"] = {
            "uid": top_res_event["uid"],
            "name": top_res_event["name"],
            "total_resources": top_res_event["total_resources"],
            "formatted_resources": (
                format_minutes(int(top_res_event["total_resources"]))
                if top_res_event["total_resources"] > 0
                else "0m"
            ),
        }

    # Top events
    top_events = sorted(
        events_data,
        key=lambda ev: (ev["submission_count"], ev["total_resources"]),
        reverse=True,
    )[:5]

    return {
        "time_range": valid_range,
        "total_events": total_events,
        "total_submissions": total_submissions,
        "total_unique_players": total_unique_players,
        "total_alliances": total_alliances,
        "total_assigned_slots": total_assigned_slots,
        "total_locked_slots": total_locked_slots,
        "global_fill_rate": global_fill_rate,
        "global_lock_rate": global_lock_rate,
        "total_resources_pledged": total_resources_pledged,
        "avg_submissions_per_event": avg_submissions_per_event,
        "buff_distribution": buff_distribution,
        "peak_time_slots": peak_time_slots,
        "superlatives": superlatives,
        "top_events": top_events,
        "events": events_data,
    }
