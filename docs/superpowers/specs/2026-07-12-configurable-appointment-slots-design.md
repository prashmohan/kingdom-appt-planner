# Design Spec: Configurable 48 vs 49 Appointment Slots

This document outlines the design to support configurable appointment slots (48 vs 49) per KvK event. This allows kingdoms to choose between the legacy 49-slot format (starting 15 minutes before the day, wrapping T-15m to T+15m next day) and a standard 48-slot format (aligned perfectly with 00:00 to 24:00).

## 1. User Review Required
No breaking changes are introduced. Standard backward compatibility is maintained for existing events, which default to 49 slots.

## 2. Database Schema Changes
We will introduce a `slot_count` column to the `events` table.

```sql
ALTER TABLE events ADD COLUMN slot_count INTEGER DEFAULT 49;
```

In `app/database.py`'s `init_db()` function:
```python
    # 1. Ensure 'events' table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            active_days TEXT NOT NULL,
            admin_secret TEXT NOT NULL,
            slot_count INTEGER DEFAULT 49,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Check if 'slot_count' column exists in existing database
    cursor.execute("PRAGMA table_info(events)")
    columns = [column[1] for column in cursor.fetchall()]
    if "slot_count" not in columns:
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN slot_count INTEGER DEFAULT 49")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
```

## 3. Slot Label Generation
In `app/__init__.py`, `generate_slot_labels()` will accept a `slot_count` argument and dynamically format starting/ending times:

```python
def generate_slot_labels(slot_count=49):
    labels = []
    for i in range(slot_count):
        if slot_count == 48:
            start_total_minutes = i * 30
        else:
            start_total_minutes = (i * 30) - 15

        if start_total_minutes < 0:
            start_total_minutes += 24 * 60

        start_hour = start_total_minutes // 60
        start_min = start_total_minutes % 60

        end_total_minutes = start_total_minutes + 30
        end_hour = (end_total_minutes // 60) % 24
        end_min = end_total_minutes % 60

        labels.append(
            f"{start_hour:02d}:{start_min:02d}-\u200b{end_hour:02d}:{end_min:02d}"
        )
    return labels
```

## 4. Flask Routes & Template Context

### UI Selection on Event Creation (`app/templates/index.html`)
Admins will select the slot format when creating a new event. We default to 49 slots.
```html
<div class="mb-6">
    <label class="block text-sm font-medium text-gray-300 mb-2">Appointment Format</label>
    <div class="flex gap-4">
        <label class="inline-flex items-center">
            <input type="radio" name="slot_count" value="49" class="form-radio text-kvk-gold focus:ring-kvk-gold bg-kvk-gray-700 border-kvk-gray-700" checked>
            <span class="ml-2 text-gray-300">49 slots (T-15m to T+15m next day)</span>
        </label>
        <label class="inline-flex items-center">
            <input type="radio" name="slot_count" value="48" class="form-radio text-kvk-gold focus:ring-kvk-gold bg-kvk-gray-700 border-kvk-gray-700">
            <span class="ml-2 text-gray-300">48 slots (00:00 to 24:00)</span>
        </label>
    </div>
</div>
```

### Route Creation handler (`app/__init__.py`)
Capture `slot_count` in `/create`:
```python
slot_count = int(request.form.get("slot_count", "49"))
```
And execute insertion including `slot_count`.

### Context Processor (`app/__init__.py`)
Provide dynamic `slot_labels` template context:
```python
@app.context_processor
def inject_global_config():
    slot_count = 49
    if request.view_args and "event_uid" in request.view_args:
        db = database.get_db()
        event = db.execute(
            "SELECT slot_count FROM events WHERE uid = ?",
            (request.view_args["event_uid"],),
        ).fetchone()
        if event and "slot_count" in event.keys() and event["slot_count"] is not None:
            slot_count = event["slot_count"]
    return dict(
        slot_labels=generate_slot_labels(slot_count),
        enable_screenshot_upload=Config.ENABLE_SCREENSHOT_UPLOAD,
        ga_measurement_id=Config.GA_MEASUREMENT_ID,
    )
```

## 5. Backend Logic Updates

### Algorithm (`app/logic.py`)
In `run_distribution_algorithm`, fetch `slot_count` from `events` and replace the hardcoded `49` range limits and length constraints:
```python
    event = db.execute(
        "SELECT active_days, slot_count FROM events WHERE uid = ?", (event_uid,)
    ).fetchone()
    ...
    slot_count = event["slot_count"] if "slot_count" in event.keys() else 49
    if slot_count is None:
        slot_count = 49
    ...
    # Demand dict and feasible slot verification:
    slot_demand = {i: 0 for i in range(slot_count)}
    ...
    feasible_slots = [
        s for s in feasible_slots if isinstance(s, int) and 0 <= s < slot_count
    ]
```

### Dashboard logic (`app/__init__.py`)
In `admin_dashboard(event_uid)`:
```python
    slot_count = event["slot_count"] if "slot_count" in event.keys() else 49
    if slot_count is None:
        slot_count = 49
    ...
    slot_density = {day: [0] * slot_count for day in active_days}
    slot_players = {day: {i: [] for i in range(slot_count)} for day in active_days}
    ...
    # Requested Slots filter bounds checks:
    requested_labels = [
        slot_labels[i] for i in feasible_slots if 0 <= i < slot_count
    ]
    ...
    if 0 <= slot_index < slot_count:
    ...
    available_slots[day] = [
        i for i in range(slot_count) if i not in assigned_slots_for_day
    ]
```

## 6. HTML Template Updates
Replace occurrences of `range(49)` with `range(slot_labels|length)` in the following templates:
- `app/templates/admin_dashboard.html`
- `app/templates/locked_appointments.html`
- `app/templates/player_form.html`
- `app/templates/public_schedule.html`

## 7. Verification Plan
- Create test KvK events with 48 and 49 slots.
- Verify slot label outputs using new unit tests.
- Ensure correct limits application in the scheduling distribution algorithm.
- Verify UI rendering behavior dynamically loops correct amounts of slots.
