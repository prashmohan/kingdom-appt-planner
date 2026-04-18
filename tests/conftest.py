import pytest
import os
import tempfile
import sqlite3
from app import create_app
from app import database

@pytest.fixture
def app():
    # Create a temporary file for the database
    db_fd, db_path = tempfile.mkstemp()
    
    # Configure the app for testing
    app = create_app()
    app.config.update({
        "TESTING": True,
        "DATABASE_PATH": db_path,
        "WTF_CSRF_ENABLED": False,
    })

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
