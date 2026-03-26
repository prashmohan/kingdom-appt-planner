import sqlite3
import json
from . import database

def run_distribution_algorithm(event_uid):
    db = database.get_db()
    db.row_factory = sqlite3.Row

    # Get the active day types for the event
    event = db.execute("SELECT active_days FROM events WHERE uid = ?", (event_uid,)).fetchone()
    if not event:
        return

    active_days = [day for day, is_active in json.loads(event['active_days']).items() if is_active]

    # Reset all submissions for the event to 'Pending' before starting
    db.execute("UPDATE submissions SET status = 'Pending' WHERE event_uid = ?", (event_uid,))

    # Loop through each active day and run the distribution for it
    for day_type in active_days:
        # 1. Preparation for the current day_type
        # Clear all non-locked assignments for this specific day
        db.execute("DELETE FROM assignments WHERE event_uid = ? AND day_type = ? AND is_locked = 0", (event_uid, day_type))
        
        # Fetch submissions specifically for this day_type
        submissions = db.execute("SELECT * FROM submissions WHERE event_uid = ? AND day_type = ? ORDER BY resources DESC, timestamp ASC", (event_uid, day_type)).fetchall()
        
        # Fetch locked assignments specifically for this day_type
        locked_assignments_raw = db.execute("SELECT * FROM assignments WHERE event_uid = ? AND day_type = ? AND is_locked = 1", (event_uid, day_type)).fetchall()
        
        taken_slots = {a['slot_index'] for a in locked_assignments_raw}
        
        # 2. Ranking & Allocation for the current day_type
        for submission in submissions:
            is_assigned = False
            # An empty feasible_slots string would be '[]'
            if not submission['feasible_slots'] or len(submission['feasible_slots']) <= 2:
                continue

            feasible_slots = json.loads(submission['feasible_slots'])
            
            for slot_index in feasible_slots:
                if slot_index not in taken_slots:
                    # Assign this slot to the player for this specific day
                    db.execute("""
                        INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked)
                        VALUES (?, ?, ?, ?, ?)
                    """, (event_uid, day_type, slot_index, submission['player_id'], 0))
                    
                    # Update submission status
                    db.execute("UPDATE submissions SET status = 'Confirmed' WHERE id = ?", (submission['id'],))
                    
                    taken_slots.add(slot_index)
                    is_assigned = True
                    break # Move to next player
            
            if not is_assigned:
                # Waitlist the player
                db.execute("UPDATE submissions SET status = 'Waitlisted' WHERE id = ?", (submission['id'],))

    db.commit()
