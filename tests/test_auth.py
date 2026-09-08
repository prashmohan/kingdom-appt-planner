"""Unit tests for app/auth.py authentication decorators."""

import sqlite3

from flask import g, session

from app import database
from app.auth import require_admin, require_superadmin


def test_require_admin_missing_event(app):
    with app.test_request_context("/admin/nonexistent?secret=any"):

        @require_admin
        def dummy_view(event_uid):
            return "ok"

        resp, code = dummy_view("nonexistent")
        assert code == 404
        assert resp == "Event not found"


def test_require_admin_missing_secret(client, app):
    client.post("/create", data={"event_name": "AuthTest"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute(
            "SELECT uid FROM events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        uid = event["uid"]

    with app.test_request_context(f"/admin/{uid}"):

        @require_admin
        def dummy_view(event_uid):
            return "ok"

        resp, code = dummy_view(uid)
        assert code == 403
        assert resp == "Forbidden"


def test_require_admin_invalid_secret(client, app):
    client.post("/create", data={"event_name": "AuthTest2"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute(
            "SELECT uid FROM events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        uid = event["uid"]

    with app.test_request_context(f"/admin/{uid}?secret=wrong_secret"):

        @require_admin
        def dummy_view(event_uid):
            return "ok"

        resp, code = dummy_view(uid)
        assert code == 403
        assert resp == "Forbidden"


def test_require_admin_valid_secret_args(client, app):
    client.post("/create", data={"event_name": "AuthTest3"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute(
            "SELECT uid, admin_secret FROM events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        uid, secret = event["uid"], event["admin_secret"]

    with app.test_request_context(f"/admin/{uid}?secret={secret}"):

        @require_admin
        def dummy_view(event_uid):
            assert g.event["uid"] == uid
            assert g.admin_secret == secret
            return "ok", 200

        resp, code = dummy_view(uid)
        assert code == 200
        assert resp == "ok"


def test_require_admin_valid_secret_form(client, app):
    client.post("/create", data={"event_name": "AuthTest4"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute(
            "SELECT uid, admin_secret FROM events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        uid, secret = event["uid"], event["admin_secret"]

    with app.test_request_context(
        f"/admin/{uid}", method="POST", data={"secret": secret}
    ):

        @require_admin
        def dummy_view(event_uid):
            assert g.event["uid"] == uid
            assert g.admin_secret == secret
            return "ok", 200

        resp, code = dummy_view(uid)
        assert code == 200
        assert resp == "ok"


def test_require_superadmin_unauthorized(app):
    with app.test_request_context("/superadmin"):

        @require_superadmin
        def dummy_view():
            return "ok"

        resp, code = dummy_view()
        assert code == 403
        assert resp == "Forbidden"


def test_require_superadmin_authorized(app):
    with app.test_request_context("/superadmin"):
        session["is_superadmin"] = True

        @require_superadmin
        def dummy_view():
            return "ok", 200

        resp, code = dummy_view()
        assert code == 200
        assert resp == "ok"
