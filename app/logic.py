import json
import re
import secrets
import sqlite3
import string
from collections import Counter, defaultdict
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
            "SELECT uid, name, active_days, admin_secret, slot_count, server_id, created_at "
            "FROM events WHERE created_at >= datetime('now', ?) "
            "ORDER BY created_at DESC"
        )
        cur = db.execute(query, (time_filters[valid_range],))
    else:
        query = (
            "SELECT uid, name, active_days, admin_secret, slot_count, server_id, created_at "
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

    # Fetch submissions and assignments for matching events using JOINs (safe against SQLite variable limits)
    if valid_range in time_filters:
        sub_query = (
            "SELECT s.id, s.event_uid, s.day_type, s.player_name, s.player_id, s.alliance_name, s.resources, s.feasible_slots, s.status, s.timestamp "
            "FROM submissions s JOIN events e ON s.event_uid = e.uid "
            "WHERE e.created_at >= datetime('now', ?)"
        )
        ass_query = (
            "SELECT a.event_uid, a.day_type, a.slot_index, a.player_id, a.is_locked "
            "FROM assignments a JOIN events e ON a.event_uid = e.uid "
            "WHERE e.created_at >= datetime('now', ?)"
        )
        sub_cur = db.execute(sub_query, (time_filters[valid_range],))
        ass_cur = db.execute(ass_query, (time_filters[valid_range],))
    else:
        sub_cur = db.execute(
            "SELECT id, event_uid, day_type, player_name, player_id, alliance_name, resources, feasible_slots, status, timestamp FROM submissions"
        )
        ass_cur = db.execute(
            "SELECT event_uid, day_type, slot_index, player_id, is_locked FROM assignments"
        )

    sub_cols = [c[0] for c in sub_cur.description] if sub_cur.description else []
    submissions = [dict(zip(sub_cols, row)) for row in sub_cur.fetchall()]

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
    event_uids = [e["uid"] for e in events]

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
            "server_id": e.get("server_id"),
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


def generate_slot_labels(slot_count: int = 49) -> list[str]:
    labels = []
    for i in range(slot_count):
        if slot_count == 48:
            start_total_minutes = i * 30
        else:
            start_total_minutes = (i * 30) - 15

        if start_total_minutes < 0:
            start_total_minutes += 24 * 60

        start_hour = start_total_minutes // 60
        start_min = start_total_minutes % 60

        end_total_minutes = start_total_minutes + 30
        end_hour = (end_total_minutes // 60) % 24
        end_min = end_total_minutes % 60

        labels.append(
            f"{start_hour:02d}:{start_min:02d}-\u200b{end_hour:02d}:{end_min:02d}"
        )
    return labels


def compute_event_insights(
    event_uid: str,
    db: sqlite3.Connection | None = None,
    max_rigid_slots: int = 8,
) -> dict[str, Any] | None:
    """
    Computes comprehensive operational and strategic insights for an event,
    covering Kingdom Firepower, Alliance Equity, and Timezone Demand/Friction.
    Returns both overall aggregates and day-by-day breakdowns.
    """
    if db is None:
        db = database.get_db()

    # Ensure row_factory is set or description is used
    db.row_factory = sqlite3.Row

    event_row = db.execute(
        "SELECT uid, name, active_days, slot_count, server_id FROM events WHERE uid = ?",
        (event_uid,),
    ).fetchone()
    if not event_row:
        return None

    slot_count = event_row["slot_count"] if event_row["slot_count"] is not None else 49
    active_days = get_ordered_active_days(event_row["active_days"])
    slot_labels = generate_slot_labels(slot_count)

    sub_cur = db.execute(
        "SELECT id, event_uid, day_type, player_name, player_id, avatar_url, backpack_url, alliance_name, resources, raw_data, feasible_slots, timestamp, status "
        "FROM submissions WHERE event_uid = ? ORDER BY resources DESC",
        (event_uid,),
    )
    sub_cols = [c[0] for c in sub_cur.description] if sub_cur.description else []
    all_submissions = [dict(zip(sub_cols, r)) for r in sub_cur.fetchall()]

    ass_cur = db.execute(
        "SELECT event_uid, day_type, slot_index, player_id, is_locked FROM assignments WHERE event_uid = ?",
        (event_uid,),
    )
    ass_cols = [c[0] for c in ass_cur.description] if ass_cur.description else []
    all_assignments = [dict(zip(ass_cols, r)) for r in ass_cur.fetchall()]

    # Map assignments: by day -> player_id -> assignment, and pair set
    all_assigned_pairs = {
        (a["day_type"], a["player_id"]) for a in all_assignments if a.get("player_id")
    }

    by_day: dict[str, Any] = {}

    for day in active_days:
        day_subs = [s for s in all_submissions if s["day_type"] == day]
        day_asses = [a for a in all_assignments if a["day_type"] == day]

        assigned_map = {a["player_id"]: a for a in day_asses if a.get("player_id")}
        assigned_pids = set(assigned_map.keys())

        # 1. Firepower metrics
        total_subs = len(day_subs)
        total_assigned = len(day_asses)
        total_res_pledged = sum(float(s["resources"] or 0) for s in day_subs)
        total_res_scheduled = sum(
            float(s["resources"] or 0)
            for s in day_subs
            if s["player_id"] in assigned_pids
        )
        total_res_unscheduled = total_res_pledged - total_res_scheduled
        scheduled_pct = (
            round((total_res_scheduled / total_res_pledged * 100), 1)
            if total_res_pledged > 0
            else 0.0
        )

        total_speedups = 0
        materials = {
            "truegold": 0,
            "tempered_truegold": 0,
            "truegold_dust": 0,
        }

        for s in day_subs:
            try:
                raw_data = json.loads(s["raw_data"])
            except (json.JSONDecodeError, TypeError):
                raw_data = {}
            if not isinstance(raw_data, dict):
                raw_data = {}
            total_speedups += int(raw_data.get("speedups", 0) or 0)
            materials["truegold"] += int(raw_data.get("truegold", 0) or 0)
            materials["tempered_truegold"] += int(
                raw_data.get("tempered_truegold", 0) or 0
            )
            materials["truegold_dust"] += int(raw_data.get("truegold_dust", 0) or 0)

        # 2. Whale Board
        whale_board = []
        for s in day_subs[:10]:
            pid = s["player_id"]
            is_assigned = pid in assigned_pids
            assigned_slot = assigned_map[pid]["slot_index"] if is_assigned else None
            assigned_slot_label = (
                slot_labels[assigned_slot]
                if (
                    is_assigned
                    and assigned_slot is not None
                    and 0 <= assigned_slot < len(slot_labels)
                )
                else None
            )
            try:
                fslots = json.loads(s["feasible_slots"])
            except (json.JSONDecodeError, TypeError):
                fslots = []
            if not isinstance(fslots, list):
                fslots = []

            whale_board.append(
                {
                    "player_name": s["player_name"],
                    "player_id": s["player_id"],
                    "alliance_name": (s["alliance_name"] or "No Alliance").strip()
                    or "No Alliance",
                    "avatar_url": s.get("avatar_url"),
                    "resources": float(s["resources"] or 0),
                    "is_assigned": is_assigned,
                    "assigned_slot": assigned_slot,
                    "assigned_slot_label": assigned_slot_label,
                    "feasible_slots_count": len(fslots),
                }
            )

        # 3. Alliance Equity
        alliance_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "total_resources": 0.0,
                "submissions_count": 0,
                "assigned_count": 0,
                "unscheduled_resources": 0.0,
            }
        )
        for s in day_subs:
            alliance = (s["alliance_name"] or "No Alliance").strip() or "No Alliance"
            res = float(s["resources"] or 0)
            alliance_data[alliance]["total_resources"] += res
            alliance_data[alliance]["submissions_count"] += 1
            if s["player_id"] in assigned_pids:
                alliance_data[alliance]["assigned_count"] += 1
            else:
                alliance_data[alliance]["unscheduled_resources"] += res

        alliance_equity = []
        for alliance_name, d in alliance_data.items():
            share_res = (
                (d["total_resources"] / total_res_pledged * 100)
                if total_res_pledged > 0
                else 0.0
            )
            share_slots = (
                (d["assigned_count"] / total_assigned * 100)
                if total_assigned > 0
                else 0.0
            )
            delta = share_slots - share_res
            acc_rate = (
                (d["assigned_count"] / d["submissions_count"] * 100)
                if d["submissions_count"] > 0
                else 0.0
            )
            avg_res = (
                (d["total_resources"] / d["submissions_count"])
                if d["submissions_count"] > 0
                else 0.0
            )
            alliance_equity.append(
                {
                    "alliance_name": alliance_name,
                    "total_resources": d["total_resources"],
                    "submissions_count": d["submissions_count"],
                    "assigned_count": d["assigned_count"],
                    "unscheduled_resources": d["unscheduled_resources"],
                    "share_of_resources_pct": round(share_res, 1),
                    "share_of_slots_pct": round(share_slots, 1),
                    "equity_delta": round(delta, 1),
                    "acceptance_rate_pct": round(acc_rate, 1),
                    "avg_resources": round(avg_res, 1),
                }
            )
        alliance_equity.sort(key=lambda a: a["total_resources"], reverse=True)

        # 4. Timezone Demand & Friction
        slot_density = [0] * slot_count
        feasible_counts = []
        for s in day_subs:
            try:
                fslots = json.loads(s["feasible_slots"])
            except (json.JSONDecodeError, TypeError):
                fslots = []
            if not isinstance(fslots, list):
                fslots = []
            feasible_counts.append(len(fslots))
            for idx in fslots:
                if 0 <= idx < slot_count:
                    slot_density[idx] += 1

        player_flexibility_avg = (
            sum(feasible_counts) / len(feasible_counts) if feasible_counts else 0.0
        )

        sorted_slots = sorted(
            [(i, slot_density[i]) for i in range(slot_count) if slot_density[i] > 0],
            key=lambda x: (-x[1], x[0]),
        )
        top_contested = [
            {
                "slot_index": i,
                "slot_label": slot_labels[i],
                "applicant_count": count,
            }
            for i, count in sorted_slots[:3]
        ]

        dead_slots = [
            {
                "slot_index": i,
                "slot_label": slot_labels[i],
                "applicant_count": slot_density[i],
            }
            for i in range(slot_count)
            if slot_density[i] == 0
        ]

        # Hourly demand (24 bins)
        hourly_demand = [
            {"hour": h, "label": f"{h:02d}:00", "applicants": 0} for h in range(24)
        ]
        for i in range(slot_count):
            if slot_count == 48:
                s_min = i * 30
            else:
                s_min = (i * 30) - 15
            if s_min < 0:
                s_min += 1440
            h = (s_min // 60) % 24
            hourly_demand[h]["applicants"] += slot_density[i]

        # Slot demand (per-slot bins, normalized against total player submissions)
        slot_demand = []
        for i in range(slot_count):
            cnt = slot_density[i]
            pct = (cnt / total_subs * 100) if total_subs > 0 else 0.0
            tier = "low" if pct < 15.0 else ("medium" if pct <= 35.0 else "high")

            # Continuous heatmap calculation: 0% -> hue 140 (emerald green) down to 40%+ -> hue 0 (crimson red)
            t = min(max(pct / 40.0, 0.0), 1.0)
            hue = 140.0 - (t * 140.0)
            slot_demand.append(
                {
                    "slot_index": i,
                    "slot_label": slot_labels[i],
                    "applicants": cnt,
                    "demand_pct": round(pct, 1),
                    "tier": tier,
                    "heatmap_gradient": (
                        f"linear-gradient(to top, hsl({hue:.0f}, 80%, 38%), hsl({hue:.0f}, 92%, 54%))"
                        if cnt > 0
                        else ""
                    ),
                    "heatmap_glow": (
                        f"0 0 6px hsla({hue:.0f}, 90%, 50%, 0.35)" if cnt > 0 else ""
                    ),
                }
            )

        # Rigid Whales (unassigned high-resource with <= 2 slots)
        rigid_whales = []
        if day_subs:
            sorted_res = sorted(float(s["resources"] or 0) for s in day_subs)
            p75_idx = min(int(len(sorted_res) * 0.75), len(sorted_res) - 1)
            threshold = sorted_res[p75_idx]
            for s in day_subs:
                if s["player_id"] not in assigned_pids:
                    try:
                        fslots = json.loads(s["feasible_slots"])
                    except (json.JSONDecodeError, TypeError):
                        fslots = []
                    if not isinstance(fslots, list):
                        fslots = []
                    res_val = float(s["resources"] or 0)
                    if len(fslots) <= max_rigid_slots and res_val >= threshold:
                        rigid_whales.append(
                            {
                                "player_name": s["player_name"],
                                "player_id": s["player_id"],
                                "alliance_name": (
                                    s["alliance_name"] or "No Alliance"
                                ).strip()
                                or "No Alliance",
                                "resources": res_val,
                                "slots_count": len(fslots),
                                "requested_slots": [
                                    slot_labels[idx]
                                    for idx in fslots
                                    if 0 <= idx < slot_count
                                ],
                            }
                        )
            rigid_whales.sort(key=lambda w: w["resources"], reverse=True)

        by_day[day] = {
            "day_type": day,
            "total_submissions": total_subs,
            "total_assigned": total_assigned,
            "total_resources_pledged": total_res_pledged,
            "total_resources_scheduled": total_res_scheduled,
            "total_resources_unscheduled": total_res_unscheduled,
            "scheduled_power_pct": scheduled_pct,
            "total_speedups_minutes": total_speedups,
            "formatted_speedups": format_minutes(total_speedups),
            "materials": materials,
            "whale_board": whale_board,
            "alliance_equity": alliance_equity,
            "player_flexibility_avg": player_flexibility_avg,
            "top_contested_slots": top_contested,
            "dead_slots": dead_slots,
            "hourly_demand": hourly_demand,
            "slot_demand": slot_demand,
            "rigid_whales": rigid_whales,
        }

    # --- Overall calculations ---
    total_submissions = len(all_submissions)
    total_assigned = len(all_assignments)
    total_resources_pledged = sum(float(s["resources"] or 0) for s in all_submissions)
    total_resources_scheduled = sum(
        float(s["resources"] or 0)
        for s in all_submissions
        if (s["day_type"], s["player_id"]) in all_assigned_pairs
    )
    total_resources_unscheduled = total_resources_pledged - total_resources_scheduled
    scheduled_power_pct = (
        round((total_resources_scheduled / total_resources_pledged * 100), 1)
        if total_resources_pledged > 0
        else 0.0
    )
    total_speedups_minutes = sum(
        by_day[d]["total_speedups_minutes"] for d in active_days
    )
    materials_combined = {
        "truegold": sum(by_day[d]["materials"]["truegold"] for d in active_days),
        "tempered_truegold": sum(
            by_day[d]["materials"]["tempered_truegold"] for d in active_days
        ),
        "truegold_dust": sum(
            by_day[d]["materials"]["truegold_dust"] for d in active_days
        ),
    }

    # Overall Whale Board
    overall_whale_board = []
    for s in all_submissions[:10]:
        pid = s["player_id"]
        day = s["day_type"]
        is_assigned = (day, pid) in all_assigned_pairs
        assigned_row = next(
            (
                a
                for a in all_assignments
                if a["day_type"] == day and a["player_id"] == pid
            ),
            None,
        )
        assigned_slot = assigned_row["slot_index"] if assigned_row else None
        assigned_slot_label = (
            slot_labels[assigned_slot]
            if (assigned_slot is not None and 0 <= assigned_slot < len(slot_labels))
            else None
        )
        try:
            fslots = json.loads(s["feasible_slots"])
        except (json.JSONDecodeError, TypeError):
            fslots = []
        if not isinstance(fslots, list):
            fslots = []

        overall_whale_board.append(
            {
                "player_name": s["player_name"],
                "player_id": s["player_id"],
                "day_type": s["day_type"],
                "alliance_name": (s["alliance_name"] or "No Alliance").strip()
                or "No Alliance",
                "avatar_url": s.get("avatar_url"),
                "resources": float(s["resources"] or 0),
                "is_assigned": is_assigned,
                "assigned_slot": assigned_slot,
                "assigned_slot_label": assigned_slot_label,
                "feasible_slots_count": len(fslots),
            }
        )

    # Multi-day players
    players_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in all_submissions:
        players_map[s["player_id"]].append(s)

    multi_day_players = []
    for pid, subs in players_map.items():
        distinct_days = sorted({s["day_type"] for s in subs})
        if len(distinct_days) >= 2:
            multi_day_players.append(
                {
                    "player_name": subs[0]["player_name"],
                    "player_id": pid,
                    "alliance_name": (subs[0]["alliance_name"] or "No Alliance").strip()
                    or "No Alliance",
                    "avatar_url": subs[0].get("avatar_url"),
                    "days": distinct_days,
                    "days_count": len(distinct_days),
                    "total_resources": sum(float(s["resources"] or 0) for s in subs),
                }
            )
    multi_day_players.sort(key=lambda p: p["total_resources"], reverse=True)

    # Cross day point breakdown
    cross_day_breakdown = [
        {
            "day_type": d,
            "total_resources": by_day[d]["total_resources_pledged"],
            "submissions": by_day[d]["total_submissions"],
            "assigned": by_day[d]["total_assigned"],
            "scheduled_pct": by_day[d]["scheduled_power_pct"],
        }
        for d in active_days
    ]

    # Overall Alliance Equity
    all_alliance_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "total_resources": 0.0,
            "submissions_count": 0,
            "assigned_count": 0,
            "unscheduled_resources": 0.0,
        }
    )
    for s in all_submissions:
        alliance = (s["alliance_name"] or "No Alliance").strip() or "No Alliance"
        res = float(s["resources"] or 0)
        all_alliance_data[alliance]["total_resources"] += res
        all_alliance_data[alliance]["submissions_count"] += 1
        if (s["day_type"], s["player_id"]) in all_assigned_pairs:
            all_alliance_data[alliance]["assigned_count"] += 1
        else:
            all_alliance_data[alliance]["unscheduled_resources"] += res

    overall_alliance_equity = []
    for alliance_name, d in all_alliance_data.items():
        share_res = (
            (d["total_resources"] / total_resources_pledged * 100)
            if total_resources_pledged > 0
            else 0.0
        )
        share_slots = (
            (d["assigned_count"] / total_assigned * 100) if total_assigned > 0 else 0.0
        )
        delta = share_slots - share_res
        acc_rate = (
            (d["assigned_count"] / d["submissions_count"] * 100)
            if d["submissions_count"] > 0
            else 0.0
        )
        avg_res = (
            (d["total_resources"] / d["submissions_count"])
            if d["submissions_count"] > 0
            else 0.0
        )
        overall_alliance_equity.append(
            {
                "alliance_name": alliance_name,
                "total_resources": d["total_resources"],
                "submissions_count": d["submissions_count"],
                "assigned_count": d["assigned_count"],
                "unscheduled_resources": d["unscheduled_resources"],
                "share_of_resources_pct": round(share_res, 1),
                "share_of_slots_pct": round(share_slots, 1),
                "equity_delta": round(delta, 1),
                "acceptance_rate_pct": round(acc_rate, 1),
                "avg_resources": round(avg_res, 1),
            }
        )
    overall_alliance_equity.sort(key=lambda a: a["total_resources"], reverse=True)

    return {
        "event_uid": event_uid,
        "active_days": active_days,
        "slot_count": slot_count,
        "overall": {
            "total_submissions": total_submissions,
            "total_assigned": total_assigned,
            "total_resources_pledged": total_resources_pledged,
            "total_resources_scheduled": total_resources_scheduled,
            "total_resources_unscheduled": total_resources_unscheduled,
            "scheduled_power_pct": scheduled_power_pct,
            "total_speedups_minutes": total_speedups_minutes,
            "formatted_speedups": format_minutes(total_speedups_minutes),
            "materials": materials_combined,
            "whale_board": overall_whale_board,
            "alliance_equity": overall_alliance_equity,
            "multi_day_players": multi_day_players,
            "cross_day_breakdown": cross_day_breakdown,
        },
        "by_day": by_day,
    }
