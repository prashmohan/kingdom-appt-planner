import sqlite3
import os
from flask import g

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'data/planner.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
    return db

def init_db():
    db = get_db()
    cursor = db.cursor()
    
    # 1. Ensure 'events' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                active_days TEXT NOT NULL,
                admin_secret TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # 2. Ensure 'submissions' table exists and has the correct schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='submissions'")
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE submissions (
                id TEXT PRIMARY KEY,
                event_uid TEXT NOT NULL,
                day_type TEXT NOT NULL,
                player_name TEXT NOT NULL,
                player_id TEXT NOT NULL,
                avatar_url TEXT,
                alliance_name TEXT,
                resources REAL NOT NULL,
                raw_data TEXT NOT NULL,
                feasible_slots TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (event_uid) REFERENCES events (uid)
            )
        """)
    else:
        # Table exists, check if 'avatar_url' column exists
        cursor.execute("PRAGMA table_info(submissions)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'avatar_url' not in columns:
            try:
                cursor.execute("ALTER TABLE submissions ADD COLUMN avatar_url TEXT")
            except sqlite3.OperationalError as e:
                # If another worker added it at the same time, ignore the error
                if "duplicate column name" not in str(e):
                    raise

    # 3. Ensure 'assignments' table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assignments'")
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE assignments (
                event_uid TEXT NOT NULL,
                day_type TEXT NOT NULL,
                slot_index INTEGER NOT NULL,
                player_id TEXT,
                is_locked BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (event_uid, day_type, slot_index),
                FOREIGN KEY (event_uid) REFERENCES events (uid)
            )
        """)
    
    db.commit()

def init_app(app):
    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()
    
    with app.app_context():
        # Ensure the data directory exists
        data_dir = os.path.dirname(DATABASE_PATH)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        init_db()

