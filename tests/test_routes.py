import pytest
import json
import sqlite3
from unittest.mock import patch, MagicMock
from app import database

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Kingdom Appointment Planner" in response.data

def test_guide_route(client):
    response = client.get('/guide')
    assert response.status_code == 200
    assert b"User Guide" in response.data or b"Tutorial" in response.data

def test_favicon(client):
    response = client.get('/favicon.ico')
    assert response.status_code == 204

def test_submission_success_route(client):
    # Covers line 289
    response = client.get('/submission-success')
    assert response.status_code == 200
    assert b"Submission Recorded" in response.data

def test_create_event(client, app):
    response = client.post('/create', data={'event_name': 'Test KvK'}, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM events WHERE name = 'Test KvK'").fetchone()
        assert event is not None

def test_player_form_page(client, app):
    client.post('/create', data={'event_name': 'Form Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        uid = db.execute("SELECT uid FROM events").fetchone()[0]
    assert client.get(f'/event/{uid}').status_code == 200

def test_player_info_proxy(client):
    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"err_code": 0, "data": {"nickname": "Mock", "avatar_image": "img.jpg"}}
        mock_post.return_value = mock_resp
        response = client.post('/api/proxy/player', json={"fid": "123"})
        assert response.status_code == 200

    assert client.post('/api/proxy/player', json={}).status_code == 400

    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"err_code": 1, "msg": "Fail"}
        mock_post.return_value = mock_resp
        assert client.post('/api/proxy/player', json={"fid": "123"}).status_code == 404

    with patch('requests.post', side_effect=Exception("Error")):
        assert client.post('/api/proxy/player', json={"fid": "123"}).status_code == 500

def test_full_flow(client, app):
    client.post('/create', data={'event_name': 'Flow'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']

    client.post(f'/event/{uid}/submit', data={
        'player_name': 'P1', 'player_id': 'p1', 'avatar_url': 'a.jpg', 'alliance_name': 'A',
        'speedups-construction': '10', 'truegold': '1', 'slots-construction': '[0]',
        'speedups-training': '10', 'slots-training': '[1]',
        'speedups-research': '10', 'truegold_dust': '1', 'slots-research': '[2]'
    })

    assert client.get(f'/admin/{uid}?secret={secret}').status_code == 200
    client.post(f'/admin/{uid}/manual_assign', data={'secret': secret, 'submission_id': f"{uid}_p1_construction", 'slot_index': '5'})
    client.post(f'/admin/{uid}/confirm', data={'secret': secret, 'day_type': 'construction', 'slot_index': '5'})
    client.post(f'/admin/{uid}/unlock', data={'secret': secret, 'day_type': 'construction', 'slot_index': '5'})
    assert client.get(f'/event/{uid}/schedule').status_code == 200
    assert client.get(f'/event/{uid}/finalized').status_code == 200
    client.post(f'/admin/{uid}/distribute', data={'secret': secret})
    client.post(f'/admin/{uid}/delete', data={'secret': secret, 'submission_id': f"{uid}_p1_construction"})

def test_error_routes(client, app):
    assert client.get('/event/none').status_code == 404
    assert client.get('/event/none/schedule').status_code == 404
    assert client.get('/event/none/finalized').status_code == 404
    assert client.get('/admin/none?secret=any').status_code == 404

    client.post('/create', data={'event_name': 'E'})
    with app.app_context():
        db = database.get_db()
        uid = db.execute("SELECT uid FROM events").fetchone()[0]
        secret = db.execute("SELECT admin_secret FROM events").fetchone()[0]
    
    assert client.get(f'/admin/{uid}?secret=bad').status_code == 403
    assert client.post(f'/admin/{uid}/distribute', data={'secret': 'bad'}).status_code == 403
    assert client.post(f'/admin/{uid}/manual_assign', data={'secret': 'bad'}).status_code == 403
    assert client.post(f'/admin/{uid}/confirm', data={'secret': 'bad'}).status_code == 403
    assert client.post(f'/admin/{uid}/unlock', data={'secret': 'bad'}).status_code == 403
    assert client.post(f'/admin/{uid}/delete', data={'secret': 'bad'}).status_code == 403
    assert client.post(f'/admin/{uid}/manual_assign', data={'secret': secret, 'slot_index': ''}).status_code == 302

def test_json_and_orphans(client, app):
    client.post('/create', data={'event_name': 'Orphan'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']
        
        # Line 361-362: Empty slots
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("empty", uid, "construction", "P", "p", "A", 0, "{}", ""))
        # Line 322-324: Bad JSON
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("bad", uid, "training", "P", "p", "A", 0, "{}", "not-json"))
        # Line 160, 340, 397-399: Orphaned assignment
        db.execute("INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
                   (uid, "construction", 15, "nobody", 1))
        db.commit()

    assert client.get(f'/admin/{uid}?secret={secret}').status_code == 200
    assert client.get(f'/event/{uid}/finalized').status_code == 200
