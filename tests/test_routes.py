import pytest
import json
import sqlite3
import os
from unittest.mock import patch, MagicMock
from app import database

def test_index_route(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Kingdom Appointment Planner" in response.data

def test_guide_route(client):
    # 1. Success
    response = client.get('/guide')
    assert response.status_code == 200
    assert b"User Guide" in response.data or b"Tutorial" in response.data

    # 2. Not Found (Missing README.md)
    if os.path.exists("README.md"):
        os.rename("README.md", "README.md.tmp")
        try:
            response = client.get('/guide')
            assert response.status_code == 404
        finally:
            os.rename("README.md.tmp", "README.md")

def test_favicon(client):
    response = client.get('/favicon.ico')
    assert response.status_code == 204

def test_submission_success_route(client):
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
        event = db.execute("SELECT uid FROM events").fetchone()
        event_uid = event['uid']

    # Test success
    resp = client.get(f'/event/{event_uid}')
    assert resp.status_code == 200
    
    # Test 404
    assert client.get('/event/nonexistent').status_code == 404

def test_player_info_proxy(client):
    # 1. Success
    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "data": {"nickname": "Mock", "avatar_image": "img.jpg"}}
        mock_post.return_value = mock_resp
        response = client.post('/api/proxy/player', json={"fid": "123"})
        assert response.status_code == 200
        data = response.get_json()
        assert data['nickname'] == "Mock"

    # 2. Missing FID
    response = client.post('/api/proxy/player', json={})
    assert response.status_code == 400

    # 3. Not found
    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 1, "msg": "Fail"}
        mock_post.return_value = mock_resp
        response = client.post('/api/proxy/player', json={"fid": "123"})
        assert response.status_code == 404

    # 4. Exception
    with patch('requests.post', side_effect=Exception("Error")):
        response = client.post('/api/proxy/player', json={"fid": "123"})
        assert response.status_code == 404

def test_refresh_players(client, app):
    # Setup event and submission
    client.post('/create', data={'event_name': 'Refresh Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']
    
    client.post(f'/event/{uid}/submit', data={
        'player_name': 'Old Name', 'player_id': 'p1', 'alliance_name': 'A',
        'speedups-construction': '10', 'slots-construction': '[0]'
    })

    # Mock API for refresh
    with patch('requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "data": {"nickname": "New Name", "avatar_image": "new.jpg"}}
        mock_post.return_value = mock_resp
        
        # Unauthorized
        resp = client.post(f'/admin/{uid}/refresh_players', data={'secret': 'wrong'})
        assert resp.status_code == 403

        # Success
        resp = client.post(f'/admin/{uid}/refresh_players', data={'secret': secret}, follow_redirects=True)
        assert resp.status_code == 200
        
        with app.app_context():
            db = database.get_db()
            db.row_factory = sqlite3.Row
            sub = db.execute("SELECT player_name, avatar_url FROM submissions WHERE player_id = 'p1'").fetchone()
            assert sub['player_name'] == "New Name"
            assert sub['avatar_url'] == "new.jpg"

def test_full_flow(client, app):
    # 1. Setup
    client.post('/create', data={'event_name': 'Flow'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']

    # 2. Submit for all days
    client.post(f'/event/{uid}/submit', data={
        'player_name': 'P1', 'player_id': 'p1', 'avatar_url': 'a.jpg', 'alliance_name': 'A',
        'speedups-construction': '10', 'truegold': '1', 'slots-construction': '[0]',
        'speedups-training': '10', 'slots-training': '[1]',
        'speedups-research': '10', 'truegold_dust': '1', 'slots-research': '[2]'
    })

    # 3. Distribution
    client.post(f'/admin/{uid}/distribute', data={'secret': secret})

    # 4. Admin Dashboard (Check if assignments render with names)
    resp = client.get(f'/admin/{uid}?secret={secret}')
    assert resp.status_code == 200
    assert b"P1" in resp.data

    # 5. Manual Assign (Locks by default)
    client.post(f'/admin/{uid}/manual_assign', data={
        'secret': secret, 'submission_id': f"{uid}_p1_construction", 'slot_index': '5'
    })

    # 6. Confirm (Keep it locked)
    client.post(f'/admin/{uid}/confirm', data={'secret': secret, 'day_type': 'construction', 'slot_index': '5'})

    # 7. Public Pages (Now with locked assignments)
    assert client.get(f'/event/{uid}/schedule').status_code == 200
    resp = client.get(f'/event/{uid}/finalized')
    assert resp.status_code == 200
    assert b"P1" in resp.data # Should be visible now

    # 8. Unlock
    client.post(f'/admin/{uid}/unlock', data={'secret': secret, 'day_type': 'construction', 'slot_index': '5'})

    # 9. Delete
    client.post(f'/admin/{uid}/delete', data={'secret': secret, 'submission_id': f"{uid}_p1_construction"})

def test_update_alliance(client, app):
    # 1. Setup
    client.post('/create', data={'event_name': 'Alliance Test'})
    with app.app_context():
        db = database.get_db()
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT uid, admin_secret FROM events").fetchone()
        uid, secret = event['uid'], event['admin_secret']

    client.post(f'/event/{uid}/submit', data={
        'player_name': 'P1', 'player_id': 'p1', 'alliance_name': 'Old',
        'speedups-construction': '10', 'slots-construction': '[0]'
    })
    submission_id = f"{uid}_p1_construction"

    # 2. Success
    resp = client.post(f'/admin/{uid}/update_alliance', data={
        'secret': secret, 'submission_id': submission_id, 'alliance_name': 'New'
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        db = database.get_db()
        sub = db.execute("SELECT alliance_name FROM submissions WHERE id = ?", (submission_id,)).fetchone()
        assert sub[0] == 'New'

    # 3. Forbidden
    assert client.post(f'/admin/{uid}/update_alliance', data={
        'secret': 'bad', 'submission_id': submission_id, 'alliance_name': 'Fail'
    }).status_code == 403

    # 4. Not Found
    assert client.post('/admin/none/update_alliance', data={
        'secret': 'any', 'submission_id': 'any', 'alliance_name': 'any'
    }).status_code == 404

def test_error_routes(client, app):
    # 404s
    assert client.get('/event/none').status_code == 404
    assert client.get('/event/none/schedule').status_code == 404
    assert client.get('/event/none/finalized').status_code == 404
    assert client.get('/admin/none?secret=any').status_code == 404
    
    # POST routes 404s
    assert client.post('/admin/none/manual_assign', data={'secret': 'any'}).status_code == 404
    assert client.post('/admin/none/distribute', data={'secret': 'any'}).status_code == 404
    assert client.post('/admin/none/confirm', data={'secret': 'any'}).status_code == 404
    assert client.post('/admin/none/unlock', data={'secret': 'any'}).status_code == 404
    assert client.post('/admin/none/delete', data={'secret': 'any'}).status_code == 404
    assert client.post('/admin/none/refresh_players', data={'secret': 'any'}).status_code == 404

    # 403s
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
        
        # Empty slots
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("empty", uid, "construction", "P", "p", "A", 0, "{}", ""))
        # Bad JSON
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("bad", uid, "training", "P", "p", "A", 0, "{}", "not-json"))
        # Orphaned assignment (submission missing)
        db.execute("INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
                   (uid, "construction", 15, "nobody", 1))
        db.commit()

    assert client.get(f'/admin/{uid}?secret={secret}').status_code == 200
    assert client.get(f'/event/{uid}/finalized').status_code == 200
