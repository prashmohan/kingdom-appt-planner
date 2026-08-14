# Configurable Appointment Slots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support configurable appointment counts (48 vs 49) per event with full database, logic, and UI support.

**Architecture:** We add a `slot_count` column to the `events` table. We parameterize `generate_slot_labels` and dynamically retrieve the slot count inside Flask routes, context processors, templates, and the scheduling distribution algorithm.

**Tech Stack:** Python 3.12, Flask 3.x, SQLite, HTML, Jinja2, Tailwind.js, pytest.

## Global Constraints
- All Python modifications must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
- Ensure all relevant unit tests verify functionality with both 48 and 49 slot lengths.

---

### Task 1: Database Migration & Schema Setup

**Files:**
- Modify: `app/database.py`
- Modify: `tests/test_basic.py`

**Interfaces:**
- Consumes: None
- Produces: `events` table with `slot_count` column

- [ ] **Step 1: Write database column and test verification**

In `tests/test_basic.py`, add a test to verify the new column and database migration:
```python
def test_database_migration_slot_count(app):
    db_fd, db_path = tempfile.mkstemp()
    try:
        conn = sqlite3.connect(db_path)
        # Create events table with legacy schema (missing slot_count)
        conn.execute(
            "CREATE TABLE events (id INTEGER PRIMARY KEY, uid TEXT UNIQUE, name TEXT, active_days TEXT, admin_secret TEXT)"
        )
        conn.commit()
        conn.close()

        # Run init_db with this existing database
        database.DATABASE_PATH = db_path
        with app.app_context():
            database.init_db()

            # Verify slot_count column exists
            db = database.get_db()
            cursor = db.execute("PRAGMA table_info(events)")
            cols = [c[1] for c in cursor.fetchall()]
            assert "slot_count" in cols
    finally:
        os.close(db_fd)
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_basic.py::test_database_migration_slot_count -v`
Expected: FAIL (AssertionError or column not found)

- [ ] **Step 3: Modify `app/database.py` to add `slot_count` column**

Update `init_db()` in `app/database.py`:
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

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_basic.py::test_database_migration_slot_count -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/database.py tests/test_basic.py
git commit -m "feat: add slot_count column to events and migrate legacy databases"
```

---

### Task 2: Parameterize Slot Label Generation

**Files:**
- Modify: `app/__init__.py:34-59`
- Modify: `tests/test_basic.py:11-20`

**Interfaces:**
- Consumes: Database schema from Task 1
- Produces: `generate_slot_labels(slot_count=49)` function

- [ ] **Step 1: Write tests for both 48 and 49 slots**

Modify `test_generate_slot_labels()` in `tests/test_basic.py`:
```python
def test_generate_slot_labels():
    # Test 49 slots (Legacy format starting at 23:45)
    labels_49 = generate_slot_labels(49)
    assert len(labels_49) == 49
    assert labels_49[0] == "23:45-\u200b00:15"
    assert labels_49[1] == "00:15-\u200b00:45"
    assert labels_49[48].endswith("23:45") or "23:45" in labels_49[48]

    # Test 48 slots (Standard format starting at 00:00)
    labels_48 = generate_slot_labels(48)
    assert len(labels_48) == 48
    assert labels_48[0] == "00:00-\u200b00:30"
    assert labels_48[1] == "00:30-\u200b01:00"
    assert labels_48[47].endswith("00:00") or "00:00" in labels_48[47]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_basic.py::test_generate_slot_labels -v`
Expected: FAIL (argument mismatch or length mismatch)

- [ ] **Step 3: Update `generate_slot_labels` in `app/__init__.py`**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_basic.py::test_generate_slot_labels -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py tests/test_basic.py
git commit -m "feat: parameterize generate_slot_labels to support 48/49 counts"
```

---

### Task 3: Scheduling Algorithm Support

**Files:**
- Modify: `app/logic.py`
- Modify: `tests/test_logic.py`

**Interfaces:**
- Consumes: `slot_count` field in `events` table
- Produces: `run_distribution_algorithm` using dynamic `slot_count` bounds

- [ ] **Step 1: Write test case in `tests/test_logic.py` for both 48 and 49 slot counts**

Add a test case in `tests/test_logic.py` verifying that scheduling works correctly under both slot counts:
```python
def test_distribution_algorithm_both_slot_lengths(app):
    db_fd, db_path = tempfile.mkstemp()
    try:
        database.DATABASE_PATH = db_path
        with app.app_context():
            database.init_db()
            db = database.get_db()

            for sc in [48, 49]:
                event_uid = f"event-test-{sc}"
                db.execute(
                    "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
                    (
                        event_uid,
                        f"Test {sc}",
                        json.dumps({"construction": True}),
                        "secret",
                        sc,
                    ),
                )
                # Player 1 wants the first slot (0)
                db.execute(
                    "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        f"sub1-{sc}",
                        event_uid,
                        "construction",
                        "Player 1",
                        f"p1-{sc}",
                        "Alliance",
                        100.0,
                        "{}",
                        json.dumps([0]),
                    ),
                )
                # Run algorithm
                logic.run_distribution_algorithm(event_uid)

                # Check assignment
                assignment = db.execute(
                    "SELECT slot_index FROM assignments WHERE event_uid = ? AND player_id = ?",
                    (event_uid, f"p1-{sc}"),
                ).fetchone()
                assert assignment is not None
                assert assignment["slot_index"] == 0
    finally:
        os.close(db_fd)
        os.unlink(db_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_logic.py::test_distribution_algorithm_both_slot_lengths -v`
Expected: FAIL (since logic.py currently hardcodes 49)

- [ ] **Step 3: Update `run_distribution_algorithm` in `app/logic.py`**

Modify:
```python
    event = db.execute(
        "SELECT active_days, slot_count FROM events WHERE uid = ?", (event_uid,)
    ).fetchone()
    if not event:
        return
```
And:
```python
    slot_count = event["slot_count"] if "slot_count" in event.keys() else 49
    if slot_count is None:
        slot_count = 49
```
Then, update all occurrences of `49` to `slot_count`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_logic.py -v`
Expected: PASS (all tests pass, including new test)

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat: support dynamic slot count in distribution algorithm"
```

---

### Task 4: UI Support, Routes & Dynamic Context

**Files:**
- Modify: `app/__init__.py`
- Modify: `app/templates/index.html`
- Modify: `tests/test_routes.py`

**Interfaces:**
- Consumes: Request parameter `event_uid` or form data
- Produces: Web route integration for configurable slots

- [ ] **Step 1: Write test checking the event creation payload and routes**

In `tests/test_routes.py`, add a test to verify event creation and rendering for both 48 and 49 configs:
```python
def test_create_event_with_slot_count(client):
    for sc in [48, 49]:
        resp = client.post(
            "/create",
            data={
                "event_name": f"Event {sc}",
                "research_day": "5",
                "slot_count": str(sc),
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Check that events database has the correct slot_count
        db = database.get_db()
        event = db.execute(
            "SELECT slot_count FROM events WHERE name = ?", (f"Event {sc}",)
        ).fetchone()
        assert event is not None
        assert event["slot_count"] == sc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_routes.py::test_create_event_with_slot_count -v`
Expected: FAIL

- [ ] **Step 3: Update `app/templates/index.html` and `app/__init__.py`**

- In `app/templates/index.html`: Add radio buttons for choosing 48 or 49 slots.
- In `app/__init__.py`:
  - Update `create_event` to parse and insert `slot_count`.
  - Update `inject_global_config` context processor to check `event_uid` from `request.view_args` and retrieve `slot_count` from database.
  - Update `admin_dashboard(event_uid)` to use `slot_count` instead of hardcoded 49.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_routes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/templates/index.html tests/test_routes.py
git commit -m "feat: add route integration and event creation support for 48/49 slots"
```

---

### Task 5: Template Loop Bounds Updates

**Files:**
- Modify: `app/templates/admin_dashboard.html`
- Modify: `app/templates/locked_appointments.html`
- Modify: `app/templates/player_form.html`
- Modify: `app/templates/public_schedule.html`

**Interfaces:**
- Consumes: Dynamic `slot_labels` context list length
- Produces: Scaled UI based on event slot count

- [ ] **Step 1: Update templates to loop over `slot_labels|length`**

In all templates listed above, change `range(49)` to `range(slot_labels|length)`.

- [ ] **Step 2: Verify the template compile and run with existing tests**

Run: `./venv/bin/pytest -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/templates/
git commit -m "feat: update templates to loop over slot_labels|length dynamically"
```
