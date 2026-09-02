import json
import string

from app import database, logic
from app.logic import (
    generate_short_uid,
    get_ordered_active_days,
    validate_custom_slug,
)


def test_algorithm_prioritization(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "test-event"
        active_days = json.dumps(
            {"construction": True, "training": True, "research": True}
        )
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Test Event", active_days, "secret"),
        )

        # Player 1 (Higher Score)
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub1",
                event_uid,
                "construction",
                "High Score",
                "player1",
                "ALL1",
                10000,
                "{}",
                "[5, 6]",
            ),
        )

        # Player 2 (Lower Score)
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub2",
                event_uid,
                "construction",
                "Low Score",
                "player2",
                "ALL1",
                5000,
                "{}",
                "[5, 6]",
            ),
        )

        db.commit()

        logic.run_distribution_algorithm(event_uid)

        # Verify Player 1 got slot 5 (their first choice) and Player 2 got slot 6 (their second choice)
        res1 = db.execute(
            "SELECT slot_index FROM assignments WHERE player_id = 'player1' AND day_type = 'construction'"
        ).fetchone()
        res2 = db.execute(
            "SELECT slot_index FROM assignments WHERE player_id = 'player2' AND day_type = 'construction'"
        ).fetchone()

        assert res1[0] == 5
        assert res2[0] == 6


def test_algorithm_lock_protection(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "lock-test"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Lock Test", json.dumps({"construction": True}), "secret"),
        )

        # Player 1: Has a locked assignment in slot 5
        db.execute(
            "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
            (event_uid, "construction", 5, "player1", 1),
        )

        # Player 2: Very high score, wants slot 5
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub2",
                event_uid,
                "construction",
                "High Score",
                "player2",
                "ALL1",
                99999,
                "{}",
                "[5, 6]",
            ),
        )

        db.commit()

        logic.run_distribution_algorithm(event_uid)

        # Player 2 should be bumped to slot 6 because slot 5 is locked
        res = db.execute(
            "SELECT slot_index FROM assignments WHERE player_id = 'player2'"
        ).fetchone()
        assert res[0] == 6


def test_algorithm_waitlist(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "waitlist-test"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Waitlist Test", json.dumps({"construction": True}), "secret"),
        )

        # Player 1 takes slot 5
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub1",
                event_uid,
                "construction",
                "P1",
                "player1",
                "ALL1",
                1000,
                "{}",
                "[5]",
            ),
        )

        # Player 2 ONLY wants slot 5
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub2",
                event_uid,
                "construction",
                "P2",
                "player2",
                "ALL1",
                500,
                "{}",
                "[5]",
            ),
        )

        db.commit()

        logic.run_distribution_algorithm(event_uid)

        # Player 2 should be waitlisted
        res = db.execute("SELECT status FROM submissions WHERE id = 'sub2'").fetchone()
        assert res[0] == "Waitlisted"


def test_algorithm_non_existent_event(app):
    with app.app_context():
        # Running algorithm on a non-existent UID should simply return (no crash)
        logic.run_distribution_algorithm("none")


def test_algorithm_empty_slots(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "empty-slots-test"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Empty Test", json.dumps({"construction": True}), "secret"),
        )

        # Player with empty slots
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub1",
                event_uid,
                "construction",
                "P1",
                "player1",
                "ALL1",
                1000,
                "{}",
                "[]",
            ),
        )

        db.commit()
        logic.run_distribution_algorithm(event_uid)

        # Should not be in assignments
        a = db.execute(
            "SELECT * FROM assignments WHERE player_id = 'player1'"
        ).fetchone()
        assert a is None


def test_algorithm_smart_spread(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "smart-spread"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Smart Spread", json.dumps({"construction": True}), "secret"),
        )

        # Player A: Score 100, Slots [1, 2]
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "subA",
                event_uid,
                "construction",
                "Player A",
                "playerA",
                "ALL1",
                100,
                "{}",
                "[1, 2]",
            ),
        )

        # Player B: Score 50, Slots [1]
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "subB",
                event_uid,
                "construction",
                "Player B",
                "playerB",
                "ALL1",
                50,
                "{}",
                "[1]",
            ),
        )

        db.commit()

        logic.run_distribution_algorithm(event_uid)

        # Player A should have picked Slot 2 because Slot 1 has higher demand (2 players requested it).
        # This leaves Slot 1 for Player B.
        resA = db.execute(
            "SELECT slot_index FROM assignments WHERE player_id = 'playerA'"
        ).fetchone()
        resB = db.execute(
            "SELECT slot_index FROM assignments WHERE player_id = 'playerB'"
        ).fetchone()

        assert resA[0] == 2
        assert resB[0] == 1


def test_algorithm_no_double_assign(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "double-assign-test"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Double Test", json.dumps({"construction": True}), "secret"),
        )

        # Player 1 has a LOCKED assignment in slot 10
        db.execute(
            "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
            (event_uid, "construction", 10, "player1", 1),
        )

        # Player 1 ALSO has a submission wanting slot 11
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "sub1",
                event_uid,
                "construction",
                "P1",
                "player1",
                "ALL1",
                1000,
                "{}",
                "[11]",
            ),
        )

        db.commit()
        logic.run_distribution_algorithm(event_uid)

        # Player 1 should STILL only have ONE assignment (the locked one)
        count = db.execute(
            "SELECT COUNT(*) FROM assignments WHERE event_uid = ? AND player_id = 'player1'",
            (event_uid,),
        ).fetchone()[0]
        assert count == 1

        # The submission should be Locked (since they have a locked assignment)
        status = db.execute(
            "SELECT status FROM submissions WHERE id = 'sub1'"
        ).fetchone()[0]
        assert status == "Locked"


def test_algorithm_bad_json(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "bad-json-test"
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            (event_uid, "Bad JSON", json.dumps({"construction": True}), "secret"),
        )

        # Submission with invalid JSON in feasible_slots
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
            ("sub1", event_uid, "construction", "P1", "p1", "A", 100, "{}", "not-json"),
        )

        db.commit()
        logic.run_distribution_algorithm(event_uid)

        # Should be waitlisted
        status = db.execute(
            "SELECT status FROM submissions WHERE id = 'sub1'"
        ).fetchone()[0]
        assert status == "Waitlisted"


def test_format_minutes():
    from app.logic import format_minutes

    assert format_minutes(0) == "0m"
    assert format_minutes(30) == "30m"
    assert format_minutes(60) == "1h"
    assert format_minutes(90) == "1h 30m"
    assert format_minutes(1440) == "1d"
    assert format_minutes(1530) == "1d 1h 30m"


def test_distribution_algorithm_both_slot_lengths(app):
    with app.app_context():
        db = database.get_db()

        for sc in [48, 49]:
            event_uid = f"event-test-{sc}"
            db.execute(
                "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
                (
                    event_uid,
                    f"Test {sc}",
                    json.dumps({"construction": True}),
                    "secret",
                    sc,
                ),
            )
            # Player 1 wants the first slot (0)
            db.execute(
                "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    f"sub1-{sc}",
                    event_uid,
                    "construction",
                    "Player 1",
                    f"p1-{sc}",
                    "Alliance",
                    100.0,
                    "{}",
                    json.dumps([0]),
                ),
            )
            # Player 2 wants the 49th slot (index 48) - which is only valid if sc == 49
            db.execute(
                "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    f"sub2-{sc}",
                    event_uid,
                    "construction",
                    "Player 2",
                    f"p2-{sc}",
                    "Alliance",
                    90.0,
                    "{}",
                    json.dumps([48]),
                ),
            )
            # Run algorithm
            logic.run_distribution_algorithm(event_uid)

            # Check assignment Player 1
            assignment1 = db.execute(
                "SELECT slot_index FROM assignments WHERE event_uid = ? AND player_id = ?",
                (event_uid, f"p1-{sc}"),
            ).fetchone()
            assert assignment1 is not None
            assert assignment1["slot_index"] == 0

            # Check assignment Player 2
            assignment2 = db.execute(
                "SELECT slot_index FROM assignments WHERE event_uid = ? AND player_id = ?",
                (event_uid, f"p2-{sc}"),
            ).fetchone()

            sub2_status = db.execute(
                "SELECT status FROM submissions WHERE id = ?",
                (f"sub2-{sc}",),
            ).fetchone()["status"]

            if sc == 48:
                assert assignment2 is None
                assert sub2_status == "Waitlisted"
            else:
                assert assignment2 is not None
                assert assignment2["slot_index"] == 48
                assert sub2_status == "Confirmed"


def test_get_ordered_active_days_day_2():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": 2,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "research",
        "training",
    ]


def test_get_ordered_active_days_day_5():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": 5,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "training",
        "research",
    ]


def test_get_ordered_active_days_default():
    config = {
        "construction": True,
        "training": True,
        "research": True,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "training",
        "research",
    ]


def test_get_ordered_active_days_string_number():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": "2",
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "research",
        "training",
    ]


def test_get_ordered_active_days_partial():
    config = {
        "construction": False,
        "training": True,
        "research": True,
        "research_day": 2,
    }
    assert get_ordered_active_days(config) == ["research", "training"]


def test_get_ordered_active_days_legacy_list():
    assert get_ordered_active_days(["construction", "research"]) == [
        "construction",
        "research",
    ]
    assert get_ordered_active_days(None) == []
    assert get_ordered_active_days("invalid") == []


def test_get_ordered_active_days_json_string():
    json_str = (
        '{"construction": true, "training": true, "research": true, "research_day": 2}'
    )
    assert get_ordered_active_days(json_str) == [
        "construction",
        "research",
        "training",
    ]


def test_generate_short_uid_length_and_charset():
    uid1 = generate_short_uid(8)
    uid2 = generate_short_uid(8)
    assert len(uid1) == 8
    assert len(uid2) == 8
    assert uid1 != uid2
    valid_chars = set(string.ascii_letters + string.digits)
    assert all(c in valid_chars for c in uid1)


def test_validate_custom_slug_valid(app):
    with app.app_context():
        db = database.get_db()
        # Valid slugs
        for slug in ["kvk-s12", "kvk_prep", "KvkSeason10", "123-abc"]:
            is_valid, err = validate_custom_slug(slug, db)
            assert is_valid is True
            assert err is None


def test_validate_custom_slug_invalid_format(app):
    with app.app_context():
        db = database.get_db()
        # Too short (< 3)
        assert validate_custom_slug("ab", db) == (
            False,
            "Custom URL code must be between 3 and 32 characters.",
        )
        # Too long (> 32)
        assert validate_custom_slug("a" * 33, db) == (
            False,
            "Custom URL code must be between 3 and 32 characters.",
        )
        # Invalid characters (spaces, special symbols)
        assert validate_custom_slug("kvk s12", db) == (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )
        assert validate_custom_slug("kvk@s12!", db) == (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )


def test_validate_custom_slug_reserved_keyword(app):
    with app.app_context():
        db = database.get_db()
        for kw in ["admin", "create", "success", "guide", "event", "static"]:
            is_valid, err = validate_custom_slug(kw, db)
            assert is_valid is False
            assert "reserved keyword" in err


def test_validate_custom_slug_duplicate(app):
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            ("existing-slug", "Test Event", "{}", "secret"),
        )
        db.commit()

        is_valid, err = validate_custom_slug("existing-slug", db)
        assert is_valid is False
        assert "already taken" in err


def test_get_superadmin_metrics_empty(temp_db):
    from app.logic import get_superadmin_metrics

    metrics = get_superadmin_metrics(temp_db, time_range="all")
    assert metrics["time_range"] == "all"
    assert metrics["total_events"] == 0
    assert metrics["total_submissions"] == 0
    assert metrics["total_unique_players"] == 0
    assert metrics["total_alliances"] == 0
    assert metrics["total_assigned_slots"] == 0
    assert metrics["total_locked_slots"] == 0
    assert metrics["global_fill_rate"] == 0.0
    assert metrics["global_lock_rate"] == 0.0
    assert metrics["total_resources_pledged"] == 0.0
    assert metrics["avg_submissions_per_event"] == 0.0
    assert metrics["buff_distribution"] == {
        "construction": {"submissions": 0, "assignments": 0},
        "training": {"submissions": 0, "assignments": 0},
        "research": {"submissions": 0, "assignments": 0},
    }
    assert metrics["peak_time_slots"] == []
    assert metrics["superlatives"]["most_contested"] is None
    assert metrics["superlatives"]["top_resources"] is None
    assert metrics["top_events"] == []
    assert metrics["events"] == []


def test_get_superadmin_metrics_with_data(temp_db):
    import json

    from app.logic import get_superadmin_metrics

    # Insert test events
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now', '-2 days'))",
        (
            "evt1",
            "Kingdom 101",
            json.dumps(["construction", "training"]),
            "sec1",
            49,
            101,
        ),
    )
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-20 days'))",
        ("evt2", "Kingdom 102", json.dumps(["construction"]), "sec2", 48),
    )

    # Insert test submissions
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s1",
            "evt1",
            "construction",
            "PlayerOne",
            "P1",
            "ALL1",
            1000000.0,
            "{}",
            json.dumps([0, 1]),
        ),
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s2",
            "evt1",
            "training",
            "PlayerTwo",
            "P2",
            "ALL2",
            2000000.0,
            "{}",
            json.dumps([1, 2]),
        ),
    )
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("evt1", "construction", 0, "P1", 1),
    )
    temp_db.commit()

    # All time
    all_metrics = get_superadmin_metrics(temp_db, time_range="all")
    assert all_metrics["total_events"] == 2
    assert all_metrics["total_submissions"] == 2
    assert all_metrics["total_unique_players"] == 2
    assert all_metrics["total_alliances"] == 2
    assert all_metrics["total_assigned_slots"] == 1
    assert all_metrics["total_locked_slots"] == 1
    assert len(all_metrics["events"]) == 2
    evt1_data = next(e for e in all_metrics["events"] if e["uid"] == "evt1")
    assert evt1_data["server_id"] == 101
    evt2_data = next(e for e in all_metrics["events"] if e["uid"] == "evt2")
    assert evt2_data["server_id"] is None

    # 1w filter (should exclude evt2 created 20 days ago)
    week_metrics = get_superadmin_metrics(temp_db, time_range="1w")
    assert week_metrics["total_events"] == 1
    assert week_metrics["total_submissions"] == 2
    assert len(week_metrics["events"]) == 1
    assert week_metrics["events"][0]["uid"] == "evt1"


def test_get_superadmin_metrics_time_ranges_and_superlatives(temp_db):
    import json

    from app.logic import get_superadmin_metrics

    # Insert events at various time points: 3 days ago, 10 days ago, 20 days ago, 40 days ago
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-3 days'))",
        ("e_3d", "Kingdom Recent", json.dumps(["construction"]), "sec3", 48),
    )
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-10 days'))",
        ("e_10d", "Kingdom 10d", json.dumps(["construction", "training"]), "sec10", 48),
    )
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-20 days'))",
        ("e_20d", "Kingdom 20d", json.dumps(["research"]), "sec20", 48),
    )
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-40 days'))",
        ("e_40d", "Kingdom Old", json.dumps(["construction"]), "sec40", 48),
    )

    # Submissions with feasible slots for peak analysis
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s1",
            "e_3d",
            "construction",
            "P1",
            "PID1",
            "AllianceA",
            500000.0,
            "{}",
            json.dumps([5, 6]),
        ),
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s2",
            "e_3d",
            "construction",
            "P2",
            "PID2",
            "AllianceA",
            1500000.0,
            "{}",
            json.dumps([5, 7]),
        ),
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s3",
            "e_10d",
            "training",
            "P3",
            "PID3",
            "AllianceB",
            3000000.0,
            "{}",
            json.dumps([5, 8]),
        ),
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "s4",
            "e_20d",
            "research",
            "P4",
            "PID4",
            "AllianceC",
            100000.0,
            "{}",
            json.dumps([12]),
        ),
    )

    # Assignments
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("e_3d", "construction", 5, "PID1", 1),
    )
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("e_10d", "training", 5, "PID3", 0),
    )
    temp_db.commit()

    # Test 1w (<= 7 days: e_3d)
    m_1w = get_superadmin_metrics(temp_db, time_range="1w")
    assert m_1w["total_events"] == 1
    assert m_1w["total_submissions"] == 2
    assert m_1w["total_resources_pledged"] == 2000000.0
    assert m_1w["global_fill_rate"] == round((1 / 48) * 100, 1)
    assert m_1w["global_lock_rate"] == 100.0

    # Test 2w (<= 14 days: e_3d, e_10d)
    m_2w = get_superadmin_metrics(temp_db, time_range="2w")
    assert m_2w["total_events"] == 2
    assert m_2w["total_submissions"] == 3
    assert m_2w["total_resources_pledged"] == 5000000.0
    assert m_2w["total_assigned_slots"] == 2
    assert m_2w["total_locked_slots"] == 1
    assert m_2w["global_lock_rate"] == 50.0

    # Test 4w (<= 28 days: e_3d, e_10d, e_20d)
    m_4w = get_superadmin_metrics(temp_db, time_range="4w")
    assert m_4w["total_events"] == 3
    assert m_4w["total_submissions"] == 4

    # Test all (all 4 events)
    m_all = get_superadmin_metrics(temp_db, time_range="all")
    assert m_all["total_events"] == 4
    assert m_all["total_submissions"] == 4

    # Check peak time slots (Slot 5 appeared 3 times in s1, s2, s3)
    assert len(m_all["peak_time_slots"]) > 0
    top_slot = m_all["peak_time_slots"][0]
    assert top_slot["count"] == 3

    # Check superlatives
    assert m_all["superlatives"]["most_contested"] is not None
    assert m_all["superlatives"]["top_resources"] is not None
    assert m_all["superlatives"]["top_resources"]["uid"] == "e_10d"
    assert m_all["superlatives"]["top_resources"]["total_resources"] == 3000000.0

    # Check top_events
    assert len(m_all["top_events"]) <= 5
    assert m_all["top_events"][0]["uid"] == "e_3d"  # 2 submissions


def test_get_superadmin_metrics_corrupted_data_and_fallbacks(temp_db):
    from app.logic import get_superadmin_metrics

    # Event with corrupted/empty JSON
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
        ("bad_evt", "Bad Event", "invalid-json", "sec_bad", None),
    )
    # Submission with invalid feasible slots and None alliance
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sub_bad",
            "bad_evt",
            "construction",
            "BadPlayer",
            "P99",
            None,
            0.0,
            "{",
            "not-json",
        ),
    )
    temp_db.commit()

    metrics = get_superadmin_metrics(temp_db, time_range="all")
    assert metrics["total_events"] == 1
    assert metrics["total_submissions"] == 1
    assert metrics["total_unique_players"] == 1
    assert metrics["total_alliances"] == 0
    assert metrics["global_fill_rate"] == 0.0
    assert metrics["events"][0]["slot_count"] == 49
    assert metrics["events"][0]["active_days"] == []


def test_compute_event_insights_empty_event(temp_db):
    from app.logic import compute_event_insights

    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
        ("empty_evt", "Empty Event", json.dumps({"construction": True}), "sec", 49),
    )
    temp_db.commit()

    insights = compute_event_insights("empty_evt", db=temp_db)
    assert insights is not None
    assert "overall" in insights
    assert "by_day" in insights
    assert "construction" in insights["by_day"]

    overall = insights["overall"]
    assert overall["total_submissions"] == 0
    assert overall["total_assigned"] == 0
    assert overall["total_resources_pledged"] == 0.0
    assert overall["scheduled_power_pct"] == 0.0
    assert overall["whale_board"] == []
    assert overall["alliance_equity"] == []
    assert overall["multi_day_players"] == []

    c_day = insights["by_day"]["construction"]
    assert c_day["total_submissions"] == 0
    assert c_day["total_assigned"] == 0
    assert c_day["player_flexibility_avg"] == 0.0
    assert c_day["top_contested_slots"] == []
    assert len(c_day["dead_slots"]) == 49
    assert c_day["rigid_whales"] == []


def test_compute_event_insights_single_day(temp_db):
    from app.logic import compute_event_insights

    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
        (
            "evt_single",
            "Single Day Event",
            json.dumps({"construction": True}),
            "sec",
            49,
        ),
    )

    # Player 1: Alliance WAR, 10000 pts, slots [2, 3], assigned to slot 2 (locked)
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sub1",
            "evt_single",
            "construction",
            "PlayerOne",
            "P1",
            "WAR",
            10000.0,
            json.dumps({"speedups": 600, "truegold": 50, "tempered_truegold": 10}),
            json.dumps([2, 3]),
            "Assigned",
        ),
    )
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("evt_single", "construction", 2, "P1", 1),
    )

    # Player 2: Alliance PEAC, 5000 pts, slots [2, 4], assigned to slot 4
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sub2",
            "evt_single",
            "construction",
            "PlayerTwo",
            "P2",
            "PEAC",
            5000.0,
            json.dumps({"speedups": 300, "truegold": 25}),
            json.dumps([2, 4]),
            "Assigned",
        ),
    )
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("evt_single", "construction", 4, "P2", 0),
    )

    # Player 3: Alliance WAR, 25000 pts (Whale!), slots [2] only (rigid!), not assigned
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sub3",
            "evt_single",
            "construction",
            "BigWhale",
            "P3",
            "WAR",
            25000.0,
            json.dumps({"speedups": 1500, "truegold": 100, "tempered_truegold": 20}),
            json.dumps([2]),
            "Pending",
        ),
    )
    temp_db.commit()

    insights = compute_event_insights("evt_single", db=temp_db)
    day = insights["by_day"]["construction"]

    # Firepower Checks
    assert day["total_submissions"] == 3
    assert day["total_assigned"] == 2
    assert day["total_resources_pledged"] == 40000.0
    assert day["total_resources_scheduled"] == 15000.0
    assert day["total_resources_unscheduled"] == 25000.0
    # 15000 / 40000 = 37.5%
    assert day["scheduled_power_pct"] == 37.5
    # Speedups sum: 600 + 300 + 1500 = 2400 minutes (40h)
    assert day["total_speedups_minutes"] == 2400
    assert day["materials"]["truegold"] == 175
    assert day["materials"]["tempered_truegold"] == 30

    # Whale Board Checks
    assert len(day["whale_board"]) == 3
    assert day["whale_board"][0]["player_name"] == "BigWhale"
    assert day["whale_board"][0]["is_assigned"] is False
    assert day["whale_board"][0]["feasible_slots_count"] == 1
    assert day["whale_board"][1]["player_name"] == "PlayerOne"
    assert day["whale_board"][1]["is_assigned"] is True
    assert day["whale_board"][1]["assigned_slot"] == 2

    # Alliance Equity Checks
    # WAR: 35,000 pts (87.5% of pts), 1 slot out of 2 (50% of slots) -> delta = 50 - 87.5 = -37.5%
    # PEAC: 5,000 pts (12.5% of pts), 1 slot out of 2 (50% of slots) -> delta = 50 - 12.5 = +37.5%
    equity_map = {a["alliance_name"]: a for a in day["alliance_equity"]}
    assert "WAR" in equity_map
    assert "PEAC" in equity_map
    war = equity_map["WAR"]
    peac = equity_map["PEAC"]

    assert war["total_resources"] == 35000.0
    assert war["share_of_resources_pct"] == 87.5
    assert war["share_of_slots_pct"] == 50.0
    assert war["equity_delta"] == -37.5
    assert war["unscheduled_resources"] == 25000.0

    assert peac["total_resources"] == 5000.0
    assert peac["share_of_resources_pct"] == 12.5
    assert peac["share_of_slots_pct"] == 50.0
    assert peac["equity_delta"] == 37.5

    # Timezone & Friction Checks
    # Slot 2 had 3 applicants (P1, P2, P3) -> Most contested
    assert len(day["top_contested_slots"]) >= 1
    assert day["top_contested_slots"][0]["slot_index"] == 2
    assert day["top_contested_slots"][0]["applicant_count"] == 3

    # Player Flexibility: P1 has 2 slots, P2 has 2 slots, P3 has 1 slot -> avg = 5/3 = 1.67
    assert round(day["player_flexibility_avg"], 2) == 1.67

    # Rigid Whale Alert: BigWhale has 25k resources (top resource holder), unassigned, only 1 slot
    assert len(day["rigid_whales"]) == 1
    assert day["rigid_whales"][0]["player_name"] == "BigWhale"
    assert day["rigid_whales"][0]["slots_count"] == 1


def test_compute_event_insights_multi_day(temp_db):
    from app.logic import compute_event_insights

    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
        (
            "evt_multi",
            "Multi Day Event",
            json.dumps({"construction": True, "training": True}),
            "sec",
            49,
        ),
    )

    # Player 1 participates in BOTH construction and training
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "m_sub1",
            "evt_multi",
            "construction",
            "MultiHero",
            "P100",
            "HERO",
            1000.0,
            json.dumps({"speedups": 100}),
            json.dumps([1]),
            "Assigned",
        ),
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "m_sub2",
            "evt_multi",
            "training",
            "MultiHero",
            "P100",
            "HERO",
            2000.0,
            json.dumps({"speedups": 200}),
            json.dumps([2]),
            "Assigned",
        ),
    )
    # Player 2 participates ONLY in training
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "m_sub3",
            "evt_multi",
            "training",
            "TrainOnly",
            "P200",
            "TRAIN",
            500.0,
            json.dumps({"speedups": 50}),
            json.dumps([3]),
            "Pending",
        ),
    )
    temp_db.commit()

    insights = compute_event_insights("evt_multi", db=temp_db)
    overall = insights["overall"]

    assert overall["total_submissions"] == 3
    assert overall["total_resources_pledged"] == 3500.0
    assert len(overall["multi_day_players"]) == 1
    assert overall["multi_day_players"][0]["player_name"] == "MultiHero"
    assert overall["multi_day_players"][0]["days_count"] == 2

    # Check by_day separation
    assert "construction" in insights["by_day"]
    assert "training" in insights["by_day"]
    assert insights["by_day"]["construction"]["total_submissions"] == 1
    assert insights["by_day"]["training"]["total_submissions"] == 2
