import pytest
import json
import sqlite3
from app import database, logic

def test_algorithm_prioritization(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "test-event"
        active_days = json.dumps({"construction": True, "training": True, "research": True})
        db.execute("INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
                   (event_uid, "Test Event", active_days, "secret"))
        
        # Player 1 (Higher Score)
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("sub1", event_uid, "construction", "High Score", "player1", "ALL1", 10000, "{}", "[5, 6]"))
        
        # Player 2 (Lower Score)
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("sub2", event_uid, "construction", "Low Score", "player2", "ALL1", 5000, "{}", "[5, 6]"))
        
        db.commit()
        
        logic.run_distribution_algorithm(event_uid)
        
        # Verify Player 1 got slot 5 (their first choice) and Player 2 got slot 6 (their second choice)
        res1 = db.execute("SELECT slot_index FROM assignments WHERE player_id = 'player1' AND day_type = 'construction'").fetchone()
        res2 = db.execute("SELECT slot_index FROM assignments WHERE player_id = 'player2' AND day_type = 'construction'").fetchone()
        
        assert res1[0] == 5
        assert res2[0] == 6

def test_algorithm_lock_protection(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "lock-test"
        db.execute("INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
                   (event_uid, "Lock Test", json.dumps({"construction": True}), "secret"))
        
        # Player 1: Has a locked assignment in slot 5
        db.execute("INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
                   (event_uid, "construction", 5, "player1", 1))
        
        # Player 2: Very high score, wants slot 5
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("sub2", event_uid, "construction", "High Score", "player2", "ALL1", 99999, "{}", "[5, 6]"))
        
        db.commit()
        
        logic.run_distribution_algorithm(event_uid)
        
        # Player 2 should be bumped to slot 6 because slot 5 is locked
        res = db.execute("SELECT slot_index FROM assignments WHERE player_id = 'player2'").fetchone()
        assert res[0] == 6

def test_algorithm_waitlist(app):
    with app.app_context():
        db = database.get_db()
        event_uid = "waitlist-test"
        db.execute("INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
                   (event_uid, "Waitlist Test", json.dumps({"construction": True}), "secret"))
        
        # Player 1 takes slot 5
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("sub1", event_uid, "construction", "P1", "player1", "ALL1", 1000, "{}", "[5]"))
        
        # Player 2 ONLY wants slot 5
        db.execute("INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                   ("sub2", event_uid, "construction", "P2", "player2", "ALL1", 500, "{}", "[5]"))
        
        db.commit()
        
        logic.run_distribution_algorithm(event_uid)
        
        # Player 2 should be waitlisted
        res = db.execute("SELECT status FROM submissions WHERE id = 'sub2'").fetchone()
        assert res[0] == 'Waitlisted'
