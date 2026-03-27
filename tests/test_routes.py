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
        active_days = json.loads(event['active_days'])
        assert active_days['construction'] is True
        assert active_days['training'] is True
        assert active_days['research'] is True

def test_player_form_page(client, app):
    # 1. Create event
    client.post('/create', data={'event_name': 'Form Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid FROM events").fetchone()
        event_uid = event['uid']

    # 2. Access form
    resp = client.get(f'/event/{event_uid}')
    assert resp.status_code == 200
    assert b"Form Test" in resp.data
    assert b"Day 1: Construction" in resp.data

def test_full_submission_and_admin_flow(client, app):
    # 1. Create event
    client.post('/create', data={'event_name': 'Full Flow Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        event_uid, secret = event['uid'], event['admin_secret']

    # 2. Submit for all 3 days
    client.post(f'/event/{event_uid}/submit', data={
        'player_name': 'Multi Day Player',
        'player_id': 'multi1',
        'alliance_name': 'MFG',
        'speedups-construction': '100',
        'truegold': '5',
        'slots-construction': '[0, 1]',
        'speedups-training': '200',
        'slots-training': '[10, 11]',
        'speedups-research': '300',
        'truegold_dust': '2',
        'slots-research': '[20, 21]'
    }, follow_redirects=True)

    # 3. Verify Submissions in DB
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        subs = db.execute("SELECT * FROM submissions WHERE event_uid = ?", (event_uid,)).fetchall()
        assert len(subs) == 3
        
        day_scores = {s['day_type']: s['resources'] for s in subs}
        assert day_scores['construction'] == 13000
        assert day_scores['training'] == 18000
        assert day_scores['research'] == 11000

    # 4. Access Admin Dashboard (Testing dictionary conversion)
    resp = client.get(f'/admin/{event_uid}?secret={secret}')
    assert resp.status_code == 200
    assert b"Admin Dashboard" in resp.data
    assert b"multi1" in resp.data
    assert b"Requested Slots:" in resp.data

    # 5. Run Distribution
    client.post(f'/admin/{event_uid}/distribute', data={'secret': secret}, follow_redirects=True)
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        assigns = db.execute("SELECT * FROM assignments WHERE event_uid = ?", (event_uid,)).fetchall()
        assert len(assigns) == 3
        slots = {a['day_type']: a['slot_index'] for a in assigns}
        assert slots['construction'] == 0
        assert slots['training'] == 10
        assert slots['research'] == 20

    # 6. Manual Assign (Override)
    client.post(f'/admin/{event_uid}/manual_assign', data={
        'secret': secret,
        'submission_id': f"{event_uid}_multi1_training",
        'slot_index': '48'
    }, follow_redirects=True)
    
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        a = db.execute("SELECT slot_index, is_locked FROM assignments WHERE player_id = 'multi1' AND day_type = 'training'").fetchone()
        assert a['slot_index'] == 48
        assert a['is_locked'] == 1

    # 7. Unlock
    client.post(f'/admin/{event_uid}/unlock', data={
        'secret': secret,
        'day_type': 'training',
        'slot_index': '48'
    }, follow_redirects=True)
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        a = db.execute("SELECT is_locked FROM assignments WHERE player_id = 'multi1' AND day_type = 'training'").fetchone()
        assert a['is_locked'] == 0

    # 8. Confirm (Lock)
    client.post(f'/admin/{event_uid}/confirm', data={
        'secret': secret,
        'day_type': 'training',
        'slot_index': '48'
    }, follow_redirects=True)
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        a = db.execute("SELECT is_locked FROM assignments WHERE player_id = 'multi1' AND day_type = 'training'").fetchone()
        assert a['is_locked'] == 1

    # 9. Public Pages
    resp = client.get(f'/event/{event_uid}/schedule')
    assert resp.status_code == 200
    assert b"multi1" in resp.data

    resp = client.get(f'/event/{event_uid}/finalized')
    assert resp.status_code == 200
    assert b"Multi Day Player" in resp.data # training is locked

    # 10. Delete
    client.post(f'/admin/{event_uid}/delete', data={
        'secret': secret,
        'submission_id': f"{event_uid}_multi1_construction"
    }, follow_redirects=True)
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        sub = db.execute("SELECT * FROM submissions WHERE id = ?", (f"{event_uid}_multi1_construction",)).fetchone()
        assert sub is None
        # Assignment should be gone too
        a = db.execute("SELECT * FROM assignments WHERE player_id = 'multi1' AND day_type = 'construction'").fetchone()
        assert a is None

def test_error_cases(client, app):
    # 1. Non-existent event
    assert client.get('/event/no-exist').status_code == 404
    assert client.get('/admin/no-exist?secret=any').status_code == 404
    assert client.get('/event/no-exist/schedule').status_code == 404
    assert client.get('/event/no-exist/finalized').status_code == 404

    # 2. Wrong secret
    client.post('/create', data={'event_name': 'Secret Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        uid = db.execute("SELECT uid FROM events").fetchone()[0]
    
    assert client.get(f'/admin/{uid}?secret=wrong').status_code == 403
    assert client.post(f'/admin/{uid}/distribute', data={'secret': 'wrong'}).status_code == 403
    assert client.post(f'/admin/{uid}/confirm', data={'secret': 'wrong'}).status_code == 403
    assert client.post(f'/admin/{uid}/unlock', data={'secret': 'wrong'}).status_code == 403
    assert client.post(f'/admin/{uid}/delete', data={'secret': 'wrong'}).status_code == 403
    assert client.post(f'/admin/{uid}/manual_assign', data={'secret': 'wrong'}).status_code == 403

    # 3. Manual assign with empty slot
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events WHERE name='Secret Test'").fetchone()
        uid, secret = event['uid'], event['admin_secret']
    
    resp = client.post(f'/admin/{uid}/manual_assign', data={'secret': secret, 'slot_index': ''})
    assert resp.status_code == 302 # Redirects back to dashboard

def test_malformed_json_in_heatmap(client, app):
    # Create event
    client.post('/create', data={'event_name': 'JSON Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']
        
        # Manually insert submission with malformed JSON slots
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("bad-json", uid, "construction", "Bad", "bad1", "NONE", 0, "{}", "not-json"))
        db.commit()

    # Admin dashboard should handle the error gracefully (line 322-324)
    resp = client.get(f'/admin/{uid}?secret={secret}')
    assert resp.status_code == 200
    assert b"Error parsing slots" in resp.data

def test_empty_feasible_slots_in_heatmap(client, app):
    # Create event
    client.post('/create', data={'event_name': 'Empty Slots Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']
        
        # Manually insert submission with empty feasible_slots (line 311-312)
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("empty-slots", uid, "construction", "Empty", "empty1", "NONE", 0, "{}", ""))
        db.commit()

    # Admin dashboard should handle the empty slots gracefully
    resp = client.get(f'/admin/{uid}?secret={secret}')
    assert resp.status_code == 200
    assert b"No slots selected" in resp.data
