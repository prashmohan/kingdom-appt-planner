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
        assigned_player_ids = {a['player_id'] for a in locked_assignments_raw}

        # Update status for players who already have locked assignments
        for pid in assigned_player_ids:
            db.execute("UPDATE submissions SET status = 'Confirmed' WHERE event_uid = ? AND day_type = ? AND player_id = ?", (event_uid, day_type, pid))

        # 2. Calculate Demand for each slot (static demand based on all submissions for this day)
        slot_demand = {i: 0 for i in range(49)}
        for sub in submissions:
            try:
                if not sub['feasible_slots']: continue
                f_slots = json.loads(sub['feasible_slots'])
                for s in f_slots:
                    if 0 <= s < 49:
                        slot_demand[s] += 1
            except (json.JSONDecodeError, TypeError):
                continue
        
        # 3. Ranking & Allocation for the current day_type
        for submission in submissions:
            # Skip if player already has a locked assignment for this day
            if submission['player_id'] in assigned_player_ids:
                continue

            is_assigned = False
            if not submission['feasible_slots'] or len(submission['feasible_slots']) <= 2:
                # No slots selected
                db.execute("UPDATE submissions SET status = 'Waitlisted' WHERE id = ?", (submission['id'],))
                continue

            try:
                feasible_slots = json.loads(submission['feasible_slots'])
            except (json.JSONDecodeError, TypeError):
                db.execute("UPDATE submissions SET status = 'Waitlisted' WHERE id = ?", (submission['id'],))
                continue
            
            # Filter to slots that are not yet taken
            available_feasible = [s for s in feasible_slots if s not in taken_slots]

            if available_feasible:
                # SMARTER LOGIC: Pick the slot with the LEAST overall demand
                # This leaves high-demand slots for players who might ONLY be able to do those slots.
                # Tie-break by slot index.
                best_slot = min(available_feasible, key=lambda s: (slot_demand[s], s))

                # Assign this slot to the player for this specific day
                db.execute("""
                    INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked)
                    VALUES (?, ?, ?, ?, ?)
                """, (event_uid, day_type, best_slot, submission['player_id'], 0))
                
                # Update submission status
                db.execute("UPDATE submissions SET status = 'Confirmed' WHERE id = ?", (submission['id'],))
                
                taken_slots.add(best_slot)
                assigned_player_ids.add(submission['player_id'])
                is_assigned = True
            
            if not is_assigned:
                # Waitlist the player
                db.execute("UPDATE submissions SET status = 'Waitlisted' WHERE id = ?", (submission['id'],))

    db.commit()
