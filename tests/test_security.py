import io
import sqlite3

from app import database
from config import Config


def test_session_cookie_security_config(app):
    """Verify session cookie security settings are configured properly."""
    assert app.config.get("SESSION_COOKIE_HTTPONLY") is True
    assert app.config.get("SESSION_COOKIE_SAMESITE") in ("Lax", "Strict")


def test_admin_constant_time_authentication(client, app):
    """Verify admin authorization works with constant-time compare_digest and rejects invalid secrets."""
    # 1. Create an event
    resp = client.post(
        "/create", data={"event_name": "Security Test Event"}, follow_redirects=False
    )
    assert resp.status_code == 302
    location = resp.headers["Location"]
    event_uid = location.split("/success/")[1].split("?")[0]
    secret = location.split("secret=")[1]

    # Valid secret
    resp_valid = client.get(f"/admin/{event_uid}?secret={secret}")
    assert resp_valid.status_code == 200

    # Wrong secret
    resp_invalid = client.get(f"/admin/{event_uid}?secret=wrongsecret")
    assert resp_invalid.status_code == 403

    # Empty secret
    resp_empty = client.get(f"/admin/{event_uid}?secret=")
    assert resp_empty.status_code == 403

    # Missing secret
    resp_missing = client.get(f"/admin/{event_uid}")
    assert resp_missing.status_code == 403


def test_security_headers_present(client):
    """Verify security headers including Referrer-Policy and HSTS."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") in (
        "no-referrer",
        "strict-origin-when-cross-origin",
    )
    assert "Strict-Transport-Security" in resp.headers


def test_audit_log_tenant_isolation(client, app):
    """Verify that viewing logs for event A does not leak event B log entries."""
    # Create Event A and Event B
    client.post("/create", data={"event_name": "Event Alpha"})
    client.post("/create", data={"event_name": "Event Beta"})

    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        ev_a = db.execute("SELECT * FROM events WHERE name = 'Event Alpha'").fetchone()
        ev_b = db.execute("SELECT * FROM events WHERE name = 'Event Beta'").fetchone()

    # Log actions for both events
    app.audit_logger.info(f"ADMIN: Action for event {ev_a['uid']}")
    app.audit_logger.info(f"ADMIN: Secret Action for event {ev_b['uid']}")

    # Request logs for Event A
    resp_a = client.get(f"/admin/{ev_a['uid']}/logs?secret={ev_a['admin_secret']}")
    assert resp_a.status_code == 200
    log_content_a = resp_a.data.decode("utf-8")
    assert ev_a["uid"] in log_content_a
    assert ev_b["uid"] not in log_content_a


def test_url_scheme_validation_on_submission(client, app):
    """Verify that javascript: or data: URIs in avatar_url are rejected or sanitized."""
    client.post("/create", data={"event_name": "URL Validation Event"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        ev = db.execute(
            "SELECT * FROM events WHERE name = 'URL Validation Event'"
        ).fetchone()
        event_uid = ev["uid"]

    # Submit with javascript: in avatar_url
    client.post(
        f"/event/{event_uid}/submit",
        data={
            "player_id": "99999",
            "player_name": "Attacker",
            "avatar_url": "javascript:alert(1)",
            "speedups-construction": "100",
            "slots-construction": "[0, 1]",
        },
    )

    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        sub = db.execute(
            "SELECT avatar_url FROM submissions WHERE event_uid = ? AND player_id = '99999'",
            (event_uid,),
        ).fetchone()
        assert sub is not None
        assert sub["avatar_url"] is None or sub["avatar_url"].startswith("http")


def test_screenshot_upload_magic_bytes(client, app, monkeypatch):
    """Verify that fake image uploads are rejected based on file content."""
    monkeypatch.setattr(Config, "ENABLE_SCREENSHOT_UPLOAD", True)

    client.post("/create", data={"event_name": "Upload Test Event"})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        ev = db.execute(
            "SELECT * FROM events WHERE name = 'Upload Test Event'"
        ).fetchone()
        event_uid = ev["uid"]

    # Attempt to upload a text file disguised as a png
    fake_png = (io.BytesIO(b"MALICIOUS_SCRIPT_CONTENT"), "evil.png")
    resp_upload = client.post(
        f"/event/{event_uid}/submit",
        data={
            "player_id": "12345",
            "player_name": "Tester",
            "speedups-construction": "100",
            "slots-construction": "[0]",
            "backpack_screenshot": fake_png,
        },
        content_type="multipart/form-data",
    )
    assert resp_upload.status_code == 400
    assert (
        b"Invalid image content" in resp_upload.data
        or b"Invalid file" in resp_upload.data
    )

    # Now upload a genuine PNG with magic bytes
    real_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    real_png = (io.BytesIO(real_png_bytes), "valid.png")
    resp_valid_upload = client.post(
        f"/event/{event_uid}/submit",
        data={
            "player_id": "12346",
            "player_name": "ValidTester",
            "speedups-construction": "100",
            "slots-construction": "[0]",
            "backpack_screenshot": real_png,
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp_valid_upload.status_code == 200
