import pytest
import json
import sqlite3
from app import database

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Kingdom Appointment Planner" in response.data

def test_create_event(client, app):
    response = client.post('/create', data={'event_name': 'Test KvK'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Event Created Successfully" in response.data
    
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE name = 'Test KvK'").fetchone()
        assert event is not None
        assert event['name'] == 'Test KvK'

def test_player_submission(client, app):
    # 1. Create event
    client.post('/create', data={'event_name': 'Sub Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid FROM events").fetchone()
        event_uid = event['uid']

    # 2. Submit form
    response = client.post(f'/event/{event_uid}/submit', data={
        'player_name': 'Test Player',
        'player_id': 'ID123',
        'alliance_name': 'TEST',
        'speedups-construction': '100',
        'truegold': '10',
        'slots-construction': '[1, 2, 3]'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Submission Recorded" in response.data

    # 3. Verify DB
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        sub = db.execute("SELECT * FROM submissions WHERE player_id = 'id123'").fetchone()
        assert sub is not None
        assert sub['day_type'] == 'construction'
        # Score = (100 * 30) + (10 * 2000) = 3000 + 20000 = 23000 (Wait, I need to check current formula in app/__init__.py)
        # Actually I see score calculation in my app/__init__.py is:
        # score = (construction_speedups * 30) + (truegold * 2000)
        assert sub['resources'] == (100 * 30) + (10 * 2000)
        assert sub['feasible_slots'] == '[1, 2, 3]'

def test_admin_access(client, app):
    # Create event
    client.post('/create', data={'event_name': 'Admin Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']

    # 1. Unauthorized
    resp = client.get(f'/admin/{uid}?secret=wrong')
    assert resp.status_code == 403

    # 2. Authorized
    resp = client.get(f'/admin/{uid}?secret={secret}')
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.data
