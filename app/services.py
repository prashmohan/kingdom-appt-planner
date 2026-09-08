"""Service layer for database operations and data access."""

import json
import sqlite3
from typing import Any


def get_event_by_uid(db: sqlite3.Connection, event_uid: str) -> sqlite3.Row | None:
    """Fetch an event row by its unique identifier."""
    db.row_factory = sqlite3.Row
    return db.execute("SELECT * FROM events WHERE uid = ?", (event_uid,)).fetchone()


def get_submissions_for_event(
    db: sqlite3.Connection, event_uid: str, day_type: str | None = None
) -> list[sqlite3.Row]:
    """Fetch submissions for an event, optionally filtered by day type."""
    db.row_factory = sqlite3.Row
    if day_type:
        return db.execute(
            "SELECT * FROM submissions WHERE event_uid = ? AND day_type = ? ORDER BY resources DESC",
            (event_uid, day_type),
        ).fetchall()
    return db.execute(
        "SELECT * FROM submissions WHERE event_uid = ? ORDER BY resources DESC",
        (event_uid,),
    ).fetchall()


def get_assignments_for_event(
    db: sqlite3.Connection, event_uid: str, day_type: str | None = None
) -> list[sqlite3.Row]:
    """Fetch assignments for an event, optionally filtered by day type."""
    db.row_factory = sqlite3.Row
    if day_type:
        return db.execute(
            "SELECT * FROM assignments WHERE event_uid = ? AND day_type = ? ORDER BY slot_index ASC",
            (event_uid, day_type),
        ).fetchall()
    return db.execute(
        "SELECT * FROM assignments WHERE event_uid = ? ORDER BY slot_index ASC",
        (event_uid,),
    ).fetchall()


def create_or_replace_submission(
    db: sqlite3.Connection,
    event_uid: str,
    day_type: str,
    player_id: str,
    player_name: str,
    alliance_name: str,
    score: int,
    raw_data: dict[str, Any],
    feasible_slots_json: str,
    avatar_url: str | None = None,
    backpack_url: str | None = None,
) -> str:
    """Insert or replace a player submission for a specific event and day type."""
    sub_id = f"{event_uid}_{player_id}_{day_type}"
    db.execute(
        "INSERT OR REPLACE INTO submissions (id, event_uid, day_type, player_name, player_id, avatar_url, backpack_url, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            sub_id,
            event_uid,
            day_type,
            player_name,
            player_id,
            avatar_url,
            backpack_url,
            alliance_name,
            score,
            json.dumps(raw_data),
            feasible_slots_json,
        ),
    )
    return sub_id


def delete_player_submissions_and_assignments(
    db: sqlite3.Connection, event_uid: str, player_id: str
) -> None:
    """Delete previous submissions and assignments when a player resubmits."""
    db.execute(
        "DELETE FROM submissions WHERE event_uid = ? AND player_id = ?",
        (event_uid, player_id),
    )
    db.execute(
        "DELETE FROM assignments WHERE event_uid = ? AND player_id = ?",
        (event_uid, player_id),
    )
