# Admin Shelf Requested Timeslots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the list of requested timeslots as styled badge pills inside the player submission details shelf in the Admin Dashboard.

**Architecture:** Attach `sub["requested_slots_labels"]` to each submission in `admin_dashboard` route in `app/__init__.py` using existing `generate_slot_labels` and `feasible_slots`, then update the shelf section in `app/templates/admin_dashboard.html` to render badge pills. Add comprehensive integration tests in `tests/test_routes.py`.

**Tech Stack:** Python 3.12, Flask 3.x, Jinja2, Tailwind CSS, SQLite, pytest, ruff.

## Global Constraints
- Must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
- Must pass `./venv/bin/pytest`.
- Maintain backwards compatibility and graceful fallback for empty or malformed `feasible_slots`.

---

### Task 1: Update Backend Route and Admin Dashboard Template

**Files:**
- Modify: `app/__init__.py:510-545`
- Modify: `app/templates/admin_dashboard.html:375-385`

**Interfaces:**
- Produces: `sub["requested_slots_labels"]: list[str]` available on each `sub` in `admin_dashboard.html`.

- [ ] **Step 1: Update `admin_dashboard` in `app/__init__.py` to set `requested_slots_labels`**

In `app/__init__.py`, update the heatmap & requested slots processing loop:
```python
for day in active_days:
    # Heatmap & Requested Slots Text
    for sub in submissions_by_day[day]:
        if not sub["feasible_slots"]:
            sub["requested_slots_text"] = "No slots selected"
            sub["requested_slots_labels"] = []
            continue
        try:
            feasible_slots = json.loads(sub["feasible_slots"])
            # Create human readable labels for hover text and shelf badges
            requested_labels = [
                slot_labels[i] for i in feasible_slots if 0 <= i < slot_count
            ]
            sub["requested_slots_labels"] = requested_labels
            sub["requested_slots_text"] = (
                ", ".join(requested_labels) if requested_labels else "No slots selected"
            )

            for slot_index in feasible_slots:
                if 0 <= slot_index < slot_count:
                    slot_density[day][slot_index] += 1
                    slot_players[day][slot_index].append(
                        {
                            "player_name": sub["player_name"],
                            "alliance_name": sub["alliance_name"],
                            "resources": sub["resources"],
                            "submission_id": sub["id"],
                        }
                    )

        except (json.JSONDecodeError, TypeError, KeyError):
            sub["requested_slots_text"] = "Error parsing slots"
            sub["requested_slots_labels"] = []
```

- [ ] **Step 2: Update `admin_dashboard.html` to render requested timeslots badges in `shelf-{{ sub.id }}`**

Inside `<tr id="shelf-{{ sub.id }}">`, right above the `<form action="{{ url_for('override_resources' ...)`:
```jinja2
                                            <div class="mb-4 pb-4 border-b border-kvk-gray-700">
                                                <div class="flex items-center justify-between mb-2">
                                                    <span class="text-xs font-bold text-gray-400 uppercase tracking-wider">
                                                        Requested Timeslots ({{ sub.requested_slots_labels|length if sub.requested_slots_labels else 0 }})
                                                    </span>
                                                </div>
                                                {% if sub.requested_slots_labels %}
                                                    <div class="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1 custom-scrollbar">
                                                        {% for slot_label in sub.requested_slots_labels %}
                                                            <span class="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-mono font-medium bg-kvk-gray-700 text-kvk-gold border border-kvk-gray-600">
                                                                {{ slot_label }}
                                                            </span>
                                                        {% endfor %}
                                                    </div>
                                                {% else %}
                                                    <p class="text-xs text-gray-500 italic">No timeslots selected.</p>
                                                {% endif %}
                                            </div>
```

- [ ] **Step 3: Run pytest to ensure existing tests pass**

Run: `./venv/bin/pytest`
Expected: PASS

- [ ] **Step 4: Run linter and commit**

```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
git add app/__init__.py app/templates/admin_dashboard.html
git commit -m "feat: display requested timeslot badges in admin submission shelf"
```

---

### Task 2: Integration Tests and Verification

**Files:**
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write integration tests in `tests/test_routes.py`**

Add tests verifying:
1. When a player submits specific slots (e.g. indices `[0, 2, 4]`), the admin dashboard shelf renders the header `Requested Timeslots (3)` and badge elements for the formatted slot labels.
2. When a player submits with empty slots `[]`, the shelf renders `Requested Timeslots (0)` and `No timeslots selected.`

```python
def test_admin_shelf_requested_timeslots_display(client):
    # 1. Create event
    resp = client.post(
        "/create",
        data={
            "event_name": "Shelf Timeslots Test",
            "research_day": "5",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    event_uid = resp.location.split("/success/")[1].split("?")[0]
    secret = resp.location.split("secret=")[1]

    # 2. Submit entry with 3 slots: [0, 2, 5]
    sub_resp = client.post(
        f"/event/{event_uid}/submit",
        data={
            "player_id": "11223344",
            "player_name": "SlotTester",
            "alliance_name": "TEST",
            "speedups-construction": "120",
            "slots-construction": "[0, 2, 5]",
        },
        follow_redirects=True,
    )
    assert sub_resp.status_code == 200

    # 3. Access Admin Dashboard
    admin_resp = client.get(f"/event/{event_uid}/admin/{secret}")
    assert admin_resp.status_code == 200
    html = admin_resp.get_data(as_text=True)

    # 4. Verify presence of shelf with Requested Timeslots count & badges
    assert "Requested Timeslots (3)" in html
    # Slot labels for 49 slots start with -15m offset: index 0 is "-00:15", index 2 is "00:30", index 5 is "02:00"
    assert "bg-kvk-gray-700 text-kvk-gold" in html


def test_admin_shelf_requested_timeslots_empty(client, app):
    # 1. Create event
    resp = client.post(
        "/create",
        data={
            "event_name": "Empty Slots Test",
            "research_day": "5",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    event_uid = resp.location.split("/success/")[1].split("?")[0]
    secret = resp.location.split("secret=")[1]

    # Insert a submission with empty/null feasible_slots directly into DB
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO submissions (id, event_uid, day_type, player_name, player_id, alliance_name, resources, raw_data, feasible_slots, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"{event_uid}_99999_construction",
                event_uid,
                "construction",
                "EmptyUser",
                "99999",
                "NULL",
                100,
                json.dumps({"speedups": 100}),
                "[]",
                "Pending",
            ),
        )
        db.commit()

    admin_resp = client.get(f"/event/{event_uid}/admin/{secret}")
    assert admin_resp.status_code == 200
    html = admin_resp.get_data(as_text=True)

    assert "Requested Timeslots (0)" in html
    assert "No timeslots selected." in html
```

- [ ] **Step 2: Run pytest to verify all tests pass**

Run: `./venv/bin/pytest`
Expected: All 80+ tests pass.

- [ ] **Step 3: Run ruff checks and formatting**

Run:
```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
```
Expected: Clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_routes.py
git commit -m "test: add integration tests for admin shelf requested timeslots"
```
