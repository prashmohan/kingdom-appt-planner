import os
import tempfile

import pytest

from app import create_app, database


@pytest.fixture
def app():
    # Create a temporary file for the database
    db_fd, db_path = tempfile.mkstemp()

    # Configure the app for testing
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "DATABASE_PATH": db_path,
            "WTF_CSRF_ENABLED": False,
        }
    )

    # Update the database module's path for the test
    database.DATABASE_PATH = db_path

    # Initialize the database
    with app.app_context():
        database.init_db()

    yield app

    # Cleanup after the test
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def temp_db(app):
    with app.app_context():
        db = database.get_db()
        yield db


@pytest.fixture
def test_event(app):
    import json

    event_data = {
        "uid": "test_event_123",
        "name": "Test Event",
        "active_days": json.dumps(
            {"construction": True, "training": True, "research": True}
        ),
        "admin_secret": "test_admin_secret_xyz",
        "slot_count": 49,
    }
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
            (
                event_data["uid"],
                event_data["name"],
                event_data["active_days"],
                event_data["admin_secret"],
                event_data["slot_count"],
            ),
        )
        db.commit()
    return event_data
