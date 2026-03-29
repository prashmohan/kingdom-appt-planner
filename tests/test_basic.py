import os
import shutil
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock
from flask import Flask, g
import pytest
from app import generate_slot_labels, database

def test_generate_slot_labels():
    labels = generate_slot_labels()
    assert len(labels) == 49
    # Check slot 0 (23:45-00:15)
    assert labels[0] == "23:45-00:15"
    # Check slot 1 (00:15-00:45)
    assert labels[1] == "00:15-00:45"
    # Check wrap around at the end
    assert labels[48].endswith("23:45") or "23:45" in labels[48]

def test_init_db_creates_directory():
    # Create a path in a new temp directory
    tmpdir = tempfile.mkdtemp()
    new_dir = os.path.join(tmpdir, "subdir")
    db_path = os.path.join(new_dir, "test.db")
    
    # Ensure subdir doesn't exist
    assert not os.path.exists(new_dir)
    
    app = Flask(__name__)
    database.DATABASE_PATH = db_path
    database.init_app(app)
    
    # Verify subdir was created
    assert os.path.exists(new_dir)
    assert os.path.exists(db_path)
    
    # Cleanup
    shutil.rmtree(tmpdir)

def test_database_migrations():
    # Create a database with an OLD schema
    db_fd, db_path = tempfile.mkstemp()
    try:
        conn = sqlite3.connect(db_path)
        # Create tables missing the new columns
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, uid TEXT UNIQUE, name TEXT, active_days TEXT, admin_secret TEXT)")
        conn.execute("CREATE TABLE submissions (id TEXT PRIMARY KEY, event_uid TEXT, day_type TEXT, player_name TEXT, player_id TEXT, alliance_name TEXT, resources REAL, raw_data TEXT, feasible_slots TEXT)")
        conn.execute("CREATE TABLE assignments (event_uid TEXT, slot_index INTEGER, player_id TEXT, is_locked BOOLEAN)")
        conn.commit()
        conn.close()

        # Run init_db with this existing database
        app = Flask(__name__)
        database.DATABASE_PATH = db_path
        with app.app_context():
            database.init_db()
            
            # Verify columns were added
            db = database.get_db()
            
            # Check submissions for avatar_url
            cursor = db.execute("PRAGMA table_info(submissions)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "avatar_url" in cols
            
            # Check assignments for day_type
            cursor = db.execute("PRAGMA table_info(assignments)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "day_type" in cols

            # Test calling it again should be fine
            database.init_db() 
    finally:
        os.close(db_fd)
        os.unlink(db_path)

def test_database_concurrency_catch():
    # Use a fresh database
    db_fd, db_path = tempfile.mkstemp()
    try:
        app = Flask(__name__)
        database.DATABASE_PATH = db_path
        
        with app.app_context():
            # Create base tables
            database.init_db()
            
            # CLEAR g._database so next get_db() calls the mock
            if hasattr(g, '_database'):
                del g._database
            
            # Mock get_db to return a mock connection
            with patch('app.database.get_db') as mock_get_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_get_db.return_value = mock_conn
                # Ensure cursor() always returns the SAME mock_cursor
                mock_conn.cursor.return_value = mock_cursor
                
                # Use lambda to always return something (table exists)
                mock_cursor.fetchone.side_effect = lambda: ("exists",)
                # Mock fetchall to return columns missing the new ones
                mock_cursor.fetchall.return_value = [[0, "id"], [1, "uid"]] 
                
                # Mock cursor.execute to raise OperationalError ONLY on ALTER TABLE
                def side_effect(sql, *args):
                    if "ALTER TABLE" in sql.upper():
                        raise sqlite3.OperationalError("duplicate column name")
                    return MagicMock()
                
                mock_cursor.execute.side_effect = side_effect
                
                # This should NOT raise an error because it's caught
                database.init_db()
                assert mock_cursor.execute.called
    finally:
        os.close(db_fd)
        os.unlink(db_path)

def test_database_concurrency_error_re_raised_submissions():
    db_fd, db_path = tempfile.mkstemp()
    try:
        app = Flask(__name__)
        database.DATABASE_PATH = db_path
        with app.app_context():
            # First initialization to create tables
            database.init_db()
            
            # CLEAR g._database
            if hasattr(g, '_database'):
                del g._database

            with patch('app.database.get_db') as mock_get_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_get_db.return_value = mock_conn
                mock_conn.cursor.return_value = mock_cursor
                
                # Tricky part:
                # 1. table existence check needs truthy
                # 2. PRAGMA call needs to be followed by fetchall returning minimal
                # 3. ALTER TABLE needs to raise error
                
                mock_cursor.fetchone.return_value = ("exists",)
                mock_cursor.fetchall.return_value = [[0, "id"]]
                
                def side_effect(sql, *args):
                    if "ALTER TABLE SUBMISSIONS" in sql.upper():
                        raise sqlite3.OperationalError("submissions error")
                    return MagicMock()
                mock_cursor.execute.side_effect = side_effect
                
                with pytest.raises(sqlite3.OperationalError) as excinfo:
                    database.init_db()
                assert "submissions error" in str(excinfo.value)
    finally:
        os.close(db_fd)
        os.unlink(db_path)

def test_database_concurrency_error_re_raised_assignments():
    db_fd, db_path = tempfile.mkstemp()
    try:
        app = Flask(__name__)
        database.DATABASE_PATH = db_path
        with app.app_context():
            database.init_db()
            
            # CLEAR g._database
            if hasattr(g, '_database'):
                del g._database

            with patch('app.database.get_db') as mock_get_db:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_get_db.return_value = mock_conn
                mock_conn.cursor.return_value = mock_cursor
                
                mock_cursor.fetchone.return_value = ("exists",)
                mock_cursor.fetchall.return_value = [[0, "id"]]
                
                def side_effect(sql, *args):
                    if "ALTER TABLE ASSIGNMENTS" in sql.upper():
                        raise sqlite3.OperationalError("assignments error")
                    return MagicMock()
                mock_cursor.execute.side_effect = side_effect
                
                with pytest.raises(sqlite3.OperationalError) as excinfo:
                    database.init_db()
                assert "assignments error" in str(excinfo.value)
    finally:
        os.close(db_fd)
        os.unlink(db_path)
