# Superadmin Interface & Global Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a protected superadmin dashboard providing global platform KPIs, time-frame filtering (1w, 2w, 4w, all), popular event highlights, and a registered events table with direct admin access.

**Architecture:** A master secret `SUPERADMIN_SECRET` in `config.py` authenticates the operator at `/superadmin?secret=...`, sets a secure session, and redirects to a clean URL. A database analytics helper `get_superadmin_metrics` aggregates platform data and time-sliced statistics. The UI in `app/templates/superadmin.html` presents KPIs, spotlights, and a searchable/sortable event table.

**Tech Stack:** Python 3.12, Flask 3.x, SQLite (WAL mode), Jinja2, Tailwind CSS, Pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-08-17-superadmin-interface-design.md`

## Global Constraints

- Python code must conform to PEP 8, formatted and linted with `ruff`.
- Route errors return standard HTTP error codes (e.g. 403 Forbidden for unauthorized superadmin access).
- Secret authentication must not leak event data or dashboard structure when unauthorized.
- `PRAGMA foreign_keys = ON` must be respected in SQLite operations.
- Zero new external heavy dependencies.

---

### Task 1: Configuration & Reserved Slugs

**Files:**
- Modify: `config.py`
- Modify: `app/logic.py:10-35`
- Test: `tests/test_basic.py`

**Interfaces:**
- Produces: `Config.SUPERADMIN_SECRET` (str)
- Produces: `"superadmin"` in `RESERVED_SLUGS` set in `app/logic.py`

- [ ] **Step 1: Write the failing tests in `tests/test_basic.py`**

```python
def test_superadmin_secret_config(app):
    from config import Config
    assert hasattr(Config, "SUPERADMIN_SECRET")
    assert isinstance(Config.SUPERADMIN_SECRET, str)
    assert len(Config.SUPERADMIN_SECRET) > 0

def test_superadmin_is_reserved_slug():
    from app.logic import validate_custom_slug
    is_valid, error = validate_custom_slug("superadmin")
    assert is_valid is False
    assert "reserved" in error.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_basic.py -k "superadmin"`
Expected: FAIL with missing attribute or slug validation passing.

- [ ] **Step 3: Implement `config.py` and `app/logic.py` changes**

In `config.py`:
```python
SUPERADMIN_SECRET = os.environ.get("SUPERADMIN_SECRET", "dev-superadmin-secret-change-me")
```

In `app/logic.py`:
Add `"superadmin"` to `RESERVED_SLUGS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_basic.py -k "superadmin" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py app/logic.py tests/test_basic.py
git commit -m "feat(config): add SUPERADMIN_SECRET and reserve superadmin slug"
```

---

### Task 2: Superadmin Analytics Computation Helper

**Files:**
- Modify: `app/logic.py`
- Test: `tests/test_logic.py`

**Interfaces:**
- Produces: `get_superadmin_metrics(db, time_range="all") -> dict`
  - Output schema:
    ```python
    {
        "time_range": "all" | "1w" | "2w" | "4w",
        "total_events": int,
        "total_submissions": int,
        "total_unique_players": int,
        "total_alliances": int,
        "total_assigned_slots": int,
        "total_locked_slots": int,
        "global_fill_rate": float, # 0.0 - 100.0
        "global_lock_rate": float, # 0.0 - 100.0
        "total_resources_pledged": float,
        "avg_submissions_per_event": float,
        "buff_distribution": {
            "construction": {"submissions": int, "assignments": int},
            "training": {"submissions": int, "assignments": int},
            "research": {"submissions": int, "assignments": int},
        },
        "peak_time_slots": list[dict], # [{"slot": str, "count": int}]
        "superlatives": {
            "most_contested": dict | None,
            "top_resources": dict | None,
        },
        "top_events": list[dict],
        "events": list[dict], # Full list for the data table
    }
    ```

- [ ] **Step 1: Write failing tests in `tests/test_logic.py`**

```python
def test_get_superadmin_metrics_empty(temp_db):
    from app.logic import get_superadmin_metrics
    metrics = get_superadmin_metrics(temp_db, time_range="all")
    assert metrics["total_events"] == 0
    assert metrics["total_submissions"] == 0
    assert metrics["total_unique_players"] == 0
    assert metrics["global_fill_rate"] == 0.0
    assert metrics["events"] == []

def test_get_superadmin_metrics_with_data(temp_db):
    import json
    from app.logic import get_superadmin_metrics
    
    # Insert test events
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-2 days'))",
        ("evt1", "Kingdom 101", json.dumps(["construction", "training"]), "sec1", 49)
    )
    temp_db.execute(
        "INSERT INTO events (uid, name, active_days, admin_secret, slot_count, created_at) VALUES (?, ?, ?, ?, ?, datetime('now', '-20 days'))",
        ("evt2", "Kingdom 102", json.dumps(["construction"]), "sec2", 48)
    )
    
    # Insert test submissions
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("s1", "evt1", "construction", "PlayerOne", "P1", "ALL1", 1000000.0, "{}", json.dumps([0, 1]))
    )
    temp_db.execute(
        "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("s2", "evt1", "training", "PlayerTwo", "P2", "ALL2", 2000000.0, "{}", json.dumps([1, 2]))
    )
    temp_db.execute(
        "INSERT INTO assignments (event_uid, day_type, slot_index, player_id, is_locked) VALUES (?, ?, ?, ?, ?)",
        ("evt1", "construction", 0, "P1", 1)
    )
    temp_db.commit()

    # All time
    all_metrics = get_superadmin_metrics(temp_db, time_range="all")
    assert all_metrics["total_events"] == 2
    assert all_metrics["total_submissions"] == 2
    assert all_metrics["total_unique_players"] == 2
    assert all_metrics["total_alliances"] == 2
    assert all_metrics["total_assigned_slots"] == 1
    assert all_metrics["total_locked_slots"] == 1
    assert len(all_metrics["events"]) == 2

    # 1w filter (should exclude evt2 created 20 days ago)
    week_metrics = get_superadmin_metrics(temp_db, time_range="1w")
    assert week_metrics["total_events"] == 1
    assert week_metrics["total_submissions"] == 2
    assert len(week_metrics["events"]) == 1
    assert week_metrics["events"][0]["uid"] == "evt1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_logic.py -k "superadmin" -v`
Expected: FAIL with `ImportError: cannot import name 'get_superadmin_metrics'`

- [ ] **Step 3: Implement `get_superadmin_metrics` in `app/logic.py`**

Implement database aggregation queries taking into account date filters (`1w`, `2w`, `4w`, `all`), calculating global KPIs, buff distributions, top time slots, superlatives, and per-event details (including slot fill % and admin URLs).

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_logic.py -k "superadmin" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/logic.py tests/test_logic.py
git commit -m "feat(logic): implement get_superadmin_metrics analytics helper"
```

---

### Task 3: Superadmin Routing & Authentication Endpoints

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `Config.SUPERADMIN_SECRET`, `get_superadmin_metrics(db, time_range)`
- Produces: `GET /superadmin`, `GET /superadmin/logout`

- [ ] **Step 1: Write failing tests in `tests/test_routes.py`**

```python
def test_superadmin_unauthorized_access(client):
    response = client.get("/superadmin")
    assert response.status_code == 403

def test_superadmin_invalid_secret(client):
    response = client.get("/superadmin?secret=invalid_secret")
    assert response.status_code == 403

def test_superadmin_event_admin_secret_rejected(client, test_event):
    response = client.get(f"/superadmin?secret={test_event['admin_secret']}")
    assert response.status_code == 403

def test_superadmin_valid_secret_sets_session_and_redirects(client, app):
    secret = app.config["SUPERADMIN_SECRET"]
    response = client.get(f"/superadmin?secret={secret}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/superadmin?range=all")

    # Follow redirect and verify 200 OK
    follow_resp = client.get("/superadmin?range=all")
    assert follow_resp.status_code == 200
    assert b"Superadmin" in follow_resp.data

def test_superadmin_time_range_filter(client, app, test_event):
    secret = app.config["SUPERADMIN_SECRET"]
    client.get(f"/superadmin?secret={secret}")
    
    response = client.get("/superadmin?range=1w")
    assert response.status_code == 200

def test_superadmin_logout(client, app):
    secret = app.config["SUPERADMIN_SECRET"]
    client.get(f"/superadmin?secret={secret}")
    
    # Authorized
    assert client.get("/superadmin").status_code == 200
    
    # Logout
    logout_resp = client.get("/superadmin/logout", follow_redirects=True)
    assert logout_resp.status_code == 200
    
    # Now unauthorized
    assert client.get("/superadmin").status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_routes.py -k "superadmin" -v`
Expected: FAIL with 404 Not Found.

- [ ] **Step 3: Implement routes in `app/__init__.py`**

In `app/__init__.py`:
- Add `superadmin` and `superadmin_logout` routes.
- Implement secret check, session flag `session["is_superadmin"] = True`, clean redirect, time range parameter handling, and template rendering.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_routes.py -k "superadmin" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py tests/test_routes.py
git commit -m "feat(routes): add superadmin dashboard and logout endpoints"
```

---

### Task 4: Superadmin Template & Interactive Dashboard UI

**Files:**
- Create: `app/templates/superadmin.html`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: Template context from `superadmin` view (`metrics`, `current_range`, `generate_slot_labels`)
- Produces: Responsive HTML dashboard with search, sort, and copy link JS.

- [ ] **Step 1: Create `app/templates/superadmin.html`**

Design elements:
1. Header with title `👑 Superadmin Console`, Time Filter toggle buttons (`1 Week`, `2 Weeks`, `4 Weeks`, `All Time`), and Logout button.
2. 4 Top Metric Cards (Total Events, Total Submissions, Unique Players, Global Fill & Lock Rate).
3. Insights Row (Buff Breakdown progress bars, Superlatives & Top 5, Peak UTC Time Slots).
4. Registered Events Table:
   - Client-side search input by Event Name or UID.
   - Column sorting.
   - Active day badges.
   - Submissions & unique player counts.
   - Fill progress bar.
   - Direct button to `/admin/<uid>?secret=<admin_secret>`.
   - "Copy Admin Link" button with toast notification.
   - Direct link to public schedule and player form.

- [ ] **Step 2: Run integration tests to verify template rendering**

Run: `./venv/bin/pytest tests/test_routes.py -k "superadmin" -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/templates/superadmin.html
git commit -m "feat(ui): create superadmin dashboard template with metrics and events table"
```

---

### Task 5: End-to-End Verification, Linting & Formatting

**Files:**
- All modified and created files

- [ ] **Step 1: Run complete test suite**

Run: `./venv/bin/pytest -v`
Expected: All tests pass with 100% success.

- [ ] **Step 2: Run ruff lint and format check**

Run: `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`
Expected: 0 errors, clean code style.

- [ ] **Step 3: Commit any final formatting adjustments**

```bash
git commit -am "style: format superadmin implementation"
```
