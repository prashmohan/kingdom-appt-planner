# Kingdom Server ID Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable admins to optionally record a Kingdom Server ID (integer, e.g. `1052`) when creating an event, persist it across the platform, and display it as `Kingdom #<server_id>` on the Player Form, Admin Dashboard, Finalized Schedule, Public Schedule, and Superadmin Console in a backwards-compatible manner.

**Architecture:** Add a nullable `server_id INTEGER` column to the `events` SQLite table with an idempotent migration in `app/database.py`. Update the `/create` route and `index.html` form to sanitize and store `server_id`. Update `app/logic.py` and Jinja templates (`player_form.html`, `admin_dashboard.html`, `locked_appointments.html`, `public_schedule.html`, `superadmin.html`) to render the badge when `server_id` is present.

**Tech Stack:** Python 3.12, Flask 3.x, SQLite, Jinja2, Tailwind CSS, Pytest.

## Global Constraints

- Python code must conform to PEP 8, formatted and linted with `ruff`.
- All schema changes must be 100% backwards-compatible and idempotent across Gunicorn workers.
- Server ID format: strict positive integer, displayed as `Kingdom #<server_id>`.
- All 104+ tests must pass with 0 regressions.

---

### Task 1: Database Migration & Schema Support for `server_id`

**Files:**
- Modify: `app/database.py:20-50`
- Test: `tests/test_basic.py`

**Interfaces:**
- Produces: `events.server_id` column in SQLite schema (INTEGER DEFAULT NULL).

- [ ] **Step 1: Write the failing test for `server_id` column and migration**

```python
def test_database_migration_server_id(app):
    from app import database

    with app.app_context():
        db = database.get_db()
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(events)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        assert "server_id" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_basic.py -k "test_database_migration_server_id" -v`
Expected: FAIL (AssertionError: "server_id" not in columns)

- [ ] **Step 3: Implement database migration in `app/database.py`**

Update `CREATE TABLE IF NOT EXISTS events` and add column migration:
```python
    cursor.execute("PRAGMA table_info(events)")
    columns = [column[1] for column in cursor.fetchall()]
    if "server_id" not in columns:
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN server_id INTEGER DEFAULT NULL")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_basic.py -k "test_database_migration_server_id" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/database.py tests/test_basic.py
git commit -m "feat(db): add server_id column and migration to events table"
```

---

### Task 2: Event Creation Route & Server ID Sanitization

**Files:**
- Modify: `app/templates/index.html:50-70`
- Modify: `app/__init__.py:159-208`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `events.server_id` column from Task 1
- Produces: `POST /create` accepting `server_id` form field and storing integer/None in DB.

- [ ] **Step 1: Write the failing tests for event creation with `server_id`**

```python
def test_create_event_with_server_id(client, app):
    from app import database

    # 1. Valid integer server ID
    resp = client.post("/create", data={"event_name": "Kingdom 1052 KvK", "server_id": "1052"})
    assert resp.status_code == 302
    with app.app_context():
        db = database.get_db()
        row = db.execute("SELECT server_id FROM events WHERE name = 'Kingdom 1052 KvK'").fetchone()
        assert row[0] == 1052

    # 2. Empty/missing server ID -> stored as NULL / None
    resp2 = client.post("/create", data={"event_name": "No Server KvK", "server_id": ""})
    assert resp2.status_code == 302
    with app.app_context():
        db = database.get_db()
        row2 = db.execute("SELECT server_id FROM events WHERE name = 'No Server KvK'").fetchone()
        assert row2[0] is None

    # 3. Invalid non-integer server ID -> falls back to None gracefully
    resp3 = client.post("/create", data={"event_name": "Invalid Server KvK", "server_id": "invalid"})
    assert resp3.status_code == 302
    with app.app_context():
        db = database.get_db()
        row3 = db.execute("SELECT server_id FROM events WHERE name = 'Invalid Server KvK'").fetchone()
        assert row3[0] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_create_event_with_server_id" -v`
Expected: FAIL

- [ ] **Step 3: Implement `server_id` field in `index.html` and parsing in `app/__init__.py`**

In `app/templates/index.html`:
```html
<div class="mb-6">
    <label for="server_id" class="block text-sm font-medium text-gray-300 mb-1">Kingdom Server ID (Optional)</label>
    <input type="number" name="server_id" id="server_id" min="1" max="999999" placeholder="e.g., 1052" class="mt-1 block w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md shadow-sm text-gray-200 focus:border-kvk-gold focus:ring focus:ring-kvk-gold focus:ring-opacity-50">
    <p class="text-xs text-gray-500 mt-1">Optional kingdom/server number (e.g. 1052) for display on player forms and schedules.</p>
</div>
```

In `app/__init__.py:create_event`:
```python
raw_server_id = request.form.get("server_id", "").strip()
server_id = None
if raw_server_id:
    try:
        parsed_id = int(raw_server_id)
        if parsed_id > 0:
            server_id = parsed_id
    except ValueError:
        server_id = None

db.execute(
    "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id) VALUES (?, ?, ?, ?, ?, ?)",
    (uid, event_name, json.dumps(active_days), admin_secret, slot_count, server_id),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_create_event_with_server_id" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/templates/index.html tests/test_routes.py
git commit -m "feat(events): add server_id field to creation form and route"
```

---

### Task 3: Display `Kingdom #ID` Across Player Form, Admin Dashboard, and Schedules

**Files:**
- Modify: `app/templates/player_form.html:60-70`
- Modify: `app/templates/admin_dashboard.html:45-60`
- Modify: `app/templates/locked_appointments.html:70-80`
- Modify: `app/templates/public_schedule.html:50-65`
- Modify: `app/__init__.py:230-650`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `event["server_id"]` from SQLite `events` row
- Produces: `Kingdom #<server_id>` badge in headers across all event pages.

- [ ] **Step 1: Write the failing tests for template badges**

```python
def test_server_id_badge_rendering(client, app):
    from app import database

    # Create event with server_id 1052
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("k1052_event", "KvK Season 12", json.dumps({"construction": True, "training": True, "research": True, "research_day": 5}), "sec123", 49, 1052),
        )
        # Create event without server_id
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("no_server_event", "Legacy KvK", json.dumps({"construction": True, "training": True, "research": True, "research_day": 5}), "sec456", 49, None),
        )
        db.commit()

    # 1. Player form
    resp_player = client.get("/event/k1052_event")
    assert "Kingdom #1052" in resp_player.get_data(as_text=True)
    resp_player_no = client.get("/event/no_server_event")
    assert "Kingdom #" not in resp_player_no.get_data(as_text=True)

    # 2. Admin dashboard
    resp_admin = client.get("/admin/k1052_event?secret=sec123")
    assert "Kingdom #1052" in resp_admin.get_data(as_text=True)

    # 3. Finalized schedule
    resp_fin = client.get("/event/k1052_event/finalized")
    assert "Kingdom #1052" in resp_fin.get_data(as_text=True)

    # 4. Public schedule
    resp_pub = client.get("/event/k1052_event/schedule")
    assert "Kingdom #1052" in resp_pub.get_data(as_text=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_server_id_badge_rendering" -v`
Expected: FAIL

- [ ] **Step 3: Update `app/__init__.py` and templates**

Ensure `event_dict` or `event` contains `server_id`:
```python
event_dict = {
    "uid": event["uid"],
    "name": event["name"],
    "active_days": active_days_config,
    "server_id": event["server_id"] if "server_id" in event.keys() else None,
}
```

In `player_form.html`:
```html
<p class="text-lg text-gray-400 mt-2 flex items-center justify-center gap-2">
    <span>{{ event.name }}</span>
    {% if event.server_id %}
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-kvk-gray-800 text-kvk-gold border border-kvk-gold/40">
            Kingdom #{{ event.server_id }}
        </span>
    {% endif %}
</p>
```

In `admin_dashboard.html`:
```html
<p class="text-sm text-gray-400 mt-1 flex items-center gap-2">
    <span>Event Administration Suite</span>
    {% if event.server_id %}
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-kvk-gray-700 text-kvk-gold border border-kvk-gold/40">
            Kingdom #{{ event.server_id }}
        </span>
    {% endif %}
</p>
```

In `locked_appointments.html` & `public_schedule.html`:
```html
<p class="text-lg text-gray-400 mt-2 flex items-center justify-center gap-2">
    <span>{{ event.name }}</span>
    {% if event.server_id %}
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-kvk-gray-800 text-kvk-gold border border-kvk-gold/40">
            Kingdom #{{ event.server_id }}
        </span>
    {% endif %}
</p>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_server_id_badge_rendering" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/templates/*.html tests/test_routes.py
git commit -m "feat(ui): display Kingdom #ID badge across player form, admin, and schedules"
```

---

### Task 4: Superadmin Analytics & Table Directory Integration

**Files:**
- Modify: `app/logic.py:274-560`
- Modify: `app/templates/superadmin.html:380-680`
- Test: `tests/test_logic.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: `events.server_id`
- Produces: `ev["server_id"]` in `get_superadmin_metrics()`, displayed in Superadmin table with `data-server` attribute and searchable.

- [ ] **Step 1: Write the failing test for `server_id` in `get_superadmin_metrics` and superadmin template**

```python
def test_superadmin_metrics_and_template_server_id(client, app):
    from app import database
    from app.logic import get_superadmin_metrics

    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, server_id) VALUES (?, ?, ?, ?, ?, ?)",
            ("sa_srv_uid", "Super Event", json.dumps({"construction": True}), "sec_sa", 49, 1088),
        )
        db.commit()
        metrics = get_superadmin_metrics(db)
        found = [e for e in metrics["events"] if e["uid"] == "sa_srv_uid"]
        assert len(found) == 1
        assert found[0]["server_id"] == 1088

    secret = app.config["SUPERADMIN_SECRET"]
    client.get(f"/superadmin?secret={secret}")
    resp = client.get("/superadmin?range=all")
    html = resp.get_data(as_text=True)
    assert "Kingdom #1088" in html
    assert 'data-server="1088"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_superadmin_metrics_and_template_server_id" -v`
Expected: FAIL

- [ ] **Step 3: Update `app/logic.py` and `app/templates/superadmin.html`**

In `app/logic.py`:
Include `server_id` in queries and in `event_dict`:
```python
"SELECT uid, name, active_days, admin_secret, slot_count, server_id, created_at FROM events ..."
...
"server_id": e.get("server_id"),
```

In `app/templates/superadmin.html`:
Add `data-server="{{ ev.server_id or '' }}"` to `<tr class="event-row">`.
In Event Name cell:
```html
<td class="py-3 px-4 font-semibold text-white max-w-[200px] md:max-w-[280px]">
    <div class="flex flex-col">
        <a href="{{ ev.public_url }}" 
           target="_blank"
           class="text-gray-100 hover:text-kvk-gold transition-colors inline-flex items-center gap-1.5 max-w-full group"
           title="View Public Schedule ({{ ev.name }})">
            <span class="truncate block">{{ ev.name }}</span>
            <svg class="w-3.5 h-3.5 flex-shrink-0 text-gray-500 group-hover:text-kvk-gold transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
        </a>
        {% if ev.server_id %}
            <span class="text-[11px] text-kvk-gold font-normal mt-0.5">Kingdom #{{ ev.server_id }}</span>
        {% endif %}
    </div>
</td>
```
In search script, include `data-server` in search query checking:
```javascript
const server = row.getAttribute('data-server') || '';
if (name.includes(query) || uid.includes(query) || server.includes(query)) {
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_routes.py -k "test_superadmin_metrics_and_template_server_id" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/logic.py app/templates/superadmin.html tests/test_logic.py tests/test_routes.py
git commit -m "feat(superadmin): include server_id in metrics and directory table search"
```

---

### Task 5: End-to-End Verification & Formatting

**Files:**
- Verification across full codebase.

- [ ] **Step 1: Run full test suite**

Run: `./venv/bin/pytest -v`
Expected: All tests pass (107+ tests).

- [ ] **Step 2: Run linter and formatting checks**

Run: `./venv/bin/ruff check . && ./venv/bin/ruff format --check .`
Expected: 0 errors, all clean.

- [ ] **Step 3: Commit any final formatting adjustments**

```bash
git add .
git commit -m "chore: final formatting and verification for kingdom server id feature" || true
```
