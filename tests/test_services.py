"""Unit tests for app/services.py."""

from app import database, services


def test_event_crud_services(app):
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, admin_secret, active_days) VALUES (?, ?, ?, ?)",
            ("svc_test_uid", "Service Test", "secret123", '{"construction":true}'),
        )
        db.commit()

        # get_event_by_uid
        event = services.get_event_by_uid(db, "svc_test_uid")
        assert event is not None
        assert event["name"] == "Service Test"

        # Non-existent
        assert services.get_event_by_uid(db, "nonexistent") is None


def test_submission_and_assignment_services(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "svc_sub_test"
        db.execute(
            "INSERT INTO events (uid, name, admin_secret, active_days) VALUES (?, ?, ?, ?)",
            (event_uid, "Sub Test", "sec", '{"construction":true}'),
        )
        db.commit()

        # create_or_replace_submission
        sub_id = services.create_or_replace_submission(
            db=db,
            event_uid=event_uid,
            day_type="construction",
            player_id="101",
            player_name="Player101",
            alliance_name="ALLI",
            score=5000,
            raw_data={"speedups": 100},
            feasible_slots_json="[0, 1]",
        )
        assert sub_id == f"{event_uid}_101_construction"
        db.commit()

        # get_submissions_for_event
        subs = services.get_submissions_for_event(db, event_uid)
        assert len(subs) == 1
        assert subs[0]["player_name"] == "Player101"

        subs_day = services.get_submissions_for_event(
            db, event_uid, day_type="construction"
        )
        assert len(subs_day) == 1
        assert (
            len(services.get_submissions_for_event(db, event_uid, day_type="training"))
            == 0
        )

        # Add an assignment
        db.execute(
            "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
            (event_uid, "construction", 0, "101", 0),
        )
        db.commit()

        asses = services.get_assignments_for_event(db, event_uid)
        assert len(asses) == 1
        assert asses[0]["player_id"] == "101"

        # delete_player_submissions_and_assignments
        services.delete_player_submissions_and_assignments(db, event_uid, "101")
        db.commit()

        assert len(services.get_submissions_for_event(db, event_uid)) == 0
        assert len(services.get_assignments_for_event(db, event_uid)) == 0


def test_submit_route_event_not_found(client):
    resp = client.post(
        "/event/nonexistent_uid_123/submit",
        data={
            "player_id": "12345",
            "player_name": "Ghost",
            "speedups-construction": "50",
            "slots-construction": "[0]",
        },
    )
    assert resp.status_code == 404
