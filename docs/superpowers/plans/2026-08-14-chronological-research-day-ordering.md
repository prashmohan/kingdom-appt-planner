# Chronological Research Day Ordering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure event days (Construction, Research, Troop Training) are displayed in chronological order across the Player Form, Admin Dashboard, Finalized Schedule, and Public Schedule based on whether the Research day is scheduled on Day 2 or Day 5.

**Architecture:** Implement a central helper function `get_ordered_active_days` in `app/logic.py` that maps each day type to its day number (`construction: 1`, `training: 4`, `research: int(research_day or 5)`) and returns the enabled days sorted chronologically. Use this helper across all routes and views in `app/__init__.py`, update `player_form.html` to render day cards dynamically in `active_days` order, and add unit and route integration tests.

**Tech Stack:** Python 3.12, Flask 3.x, Jinja2, Tailwind CSS, SQLite, pytest, ruff.

## Global Constraints
- Must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
- Must pass `./venv/bin/pytest`.
- Maintain backwards compatibility for legacy list-based `active_days` in existing records and tests.
- Retain all input IDs and element structure in `player_form.html` so existing form validation and speedup calculations continue functioning properly.

---

### Task 1: Add `get_ordered_active_days` in `app/logic.py` with Unit Tests

**Files:**
- Modify: `app/logic.py`
- Modify: `tests/test_logic.py`

**Interfaces:**
- Produces: `get_ordered_active_days(active_days_config: Union[dict, list, str, None]) -> list[str]`

- [ ] **Step 1: Write the failing tests in `tests/test_logic.py`**

Add tests to `tests/test_logic.py`:
```python
from app.logic import get_ordered_active_days


def test_get_ordered_active_days_day_2():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": 2,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "research",
        "training",
    ]


def test_get_ordered_active_days_day_5():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": 5,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "training",
        "research",
    ]


def test_get_ordered_active_days_default():
    config = {
        "construction": True,
        "training": True,
        "research": True,
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "training",
        "research",
    ]


def test_get_ordered_active_days_string_number():
    config = {
        "construction": True,
        "training": True,
        "research": True,
        "research_day": "2",
    }
    assert get_ordered_active_days(config) == [
        "construction",
        "research",
        "training",
    ]


def test_get_ordered_active_days_partial():
    config = {
        "construction": False,
        "training": True,
        "research": True,
        "research_day": 2,
    }
    assert get_ordered_active_days(config) == ["research", "training"]


def test_get_ordered_active_days_legacy_list():
    assert get_ordered_active_days(["construction", "research"]) == [
        "construction",
        "research",
    ]
    assert get_ordered_active_days(None) == []
    assert get_ordered_active_days("invalid") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_logic.py -k test_get_ordered_active_days`
Expected: FAIL (ImportError or cannot import `get_ordered_active_days`)

- [ ] **Step 3: Implement `get_ordered_active_days` in `app/logic.py`**

Add to `app/logic.py`:
```python
def get_ordered_active_days(active_days_config):
    """
    Returns active days sorted chronologically by day number.
    Supports active_days_config as a dict, list, or JSON string.
    """
    if isinstance(active_days_config, str):
        try:
            active_days_config = json.loads(active_days_config)
        except (json.JSONDecodeError, TypeError):
            return []

    if isinstance(active_days_config, list):
        return [
            d
            for d in active_days_config
            if d in ("construction", "training", "research")
        ]
    if not isinstance(active_days_config, dict):
        return []

    try:
        research_day_num = int(active_days_config.get("research_day", 5) or 5)
    except (ValueError, TypeError):
        research_day_num = 5

    day_numbers = {
        "construction": 1,
        "training": 4,
        "research": research_day_num,
    }

    active = [
        day
        for day in ["construction", "training", "research"]
        if active_days_config.get(day)
    ]
    return sorted(active, key=lambda d: day_numbers.get(d, 99))
```

Also update `run_distribution_algorithm` in `app/logic.py` where active days are loaded:
```python
    if day_type:
        active_days = [day_type]
    else:
        active_days = get_ordered_active_days(event["active_days"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/pytest tests/test_logic.py -k test_get_ordered_active_days`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
git add app/logic.py tests/test_logic.py
git commit -m "feat: add get_ordered_active_days helper with unit tests"
```

---

### Task 2: Update Backend Routes in `app/__init__.py` to Use Ordered Active Days

**Files:**
- Modify: `app/__init__.py`

**Interfaces:**
- Consumes: `get_ordered_active_days` from `app.logic`
- Produces: Correctly ordered `active_days` passed to templates and data structures in `locked_appointments`, `player_form`, `admin_dashboard`, and `public_schedule`.

- [ ] **Step 1: Update `app/__init__.py` routes**

1. Import `get_ordered_active_days` in `app/__init__.py`:
   ```python
   from .logic import (
       generate_slot_labels,
       get_ordered_active_days,
       run_distribution_algorithm,
   )
   ```

2. Update `locked_appointments` route in `app/__init__.py`:
   Replace:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = [
       day
       for day in ["construction", "training", "research"]
       if active_days_config.get(day)
   ]
   ```
   With:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = get_ordered_active_days(active_days_config)
   ```

3. Update `player_form` route in `app/__init__.py`:
   Compute `active_days` and pass to `player_form.html`:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = get_ordered_active_days(active_days_config)
   event_dict = {
       "uid": event["uid"],
       "name": event["name"],
       "active_days": active_days_config,
   }

   return render_template("player_form.html", event=event_dict, active_days=active_days)
   ```

4. Update `admin_dashboard` route in `app/__init__.py`:
   Replace:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = [
       day
       for day in ["construction", "training", "research"]
       if active_days_config.get(day)
   ]
   ```
   With:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = get_ordered_active_days(active_days_config)
   ```

5. Update `public_schedule` route in `app/__init__.py`:
   Replace:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = [
       day
       for day in ["construction", "training", "research"]
       if active_days_config.get(day)
   ]
   ```
   With:
   ```python
   active_days_config = json.loads(event["active_days"])
   active_days = get_ordered_active_days(active_days_config)
   ```

- [ ] **Step 2: Run pytest to ensure no existing tests broke**

Run: `./venv/bin/pytest`
Expected: PASS (all 67+ tests pass)

- [ ] **Step 3: Run linter and commit**

```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
git add app/__init__.py
git commit -m "feat: use get_ordered_active_days across all routes"
```

---

### Task 3: Update `player_form.html` to Render Cards in Dynamic Chronological Order

**Files:**
- Modify: `app/templates/player_form.html:108-226`

**Interfaces:**
- Consumes: `active_days` list passed from `player_form` route.

- [ ] **Step 1: Update `player_form.html` grid to loop over `active_days`**

Replace the static 3-block structure (lines 108-226) with:
```jinja2
            <div class="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
                {% for day in active_days %}
                    {% if day == 'construction' %}
                    <div class="p-4 rounded-lg bg-kvk-gray-900 border border-kvk-gray-700">
                        <h3 class="font-bold text-xl mb-2 text-amber-400">Day 1: Construction</h3>
                        <p class="text-xs text-gray-400 mb-4 italic">Enter resources and select <strong>all feasible</strong> time slots. More slots give the system more flexibility to match you.</p>
                        <div class="space-y-4 mb-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-300 mb-2">Speedups</label>
                                <div class="flex gap-2 mb-2">
                                    <button type="button" data-unit="days" data-section="construction" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Days</button>
                                    <button type="button" data-unit="hours" data-section="construction" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Hours</button>
                                    <button type="button" data-unit="minutes" data-section="construction" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gold bg-kvk-gold text-kvk-gray-900 font-bold transition">Minutes</button>
                                </div>
                                <div id="input-group-construction" class="grid grid-cols-3 gap-2">
                                    <div class="hidden" id="days-container-construction">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Days</label>
                                        <input type="number" id="days-construction" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                    <div class="hidden" id="hours-container-construction">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Hours</label>
                                        <input type="number" id="hours-construction" min="0" max="23" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                    <div id="minutes-container-construction">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Minutes</label>
                                        <input type="number" id="mins-construction" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                </div>
                                <input type="hidden" name="speedups-construction" id="speedups-construction" value="0">
                            </div>
                            <div>
                                <label for="truegold" class="block text-sm font-medium text-gray-300">TrueGold</label>
                                <input type="number" name="truegold" id="truegold" min="0" class="mt-1 block w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200">
                            </div>
                            <div>
                                <label for="tempered_truegold" class="block text-sm font-medium text-gray-300">Tempered TrueGold</label>
                                <input type="number" name="tempered_truegold" id="tempered_truegold" min="0" class="mt-1 block w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200">
                            </div>
                        </div>
                        <div id="slot-grid-construction" class="grid grid-cols-7 gap-1 mb-4">
                            {% for i in range(slot_labels|length) %}<div class="slot" data-index="{{ i }}"><div class="slot-content">{{ slot_labels[i] }}</div></div>{% endfor %}
                        </div>
                        <input type="hidden" name="slots-construction" id="slots-input-construction">
                    </div>
                    {% elif day == 'research' %}
                    <div class="p-4 rounded-lg bg-kvk-gray-900 border border-kvk-gray-700">
                        <h3 class="font-bold text-xl mb-2 text-blue-500">Day {{ event.active_days.research_day if event.active_days.research_day else '5' }}: Research</h3>
                        <p class="text-xs text-gray-400 mb-4 italic">Enter resources and select <strong>all feasible</strong> time slots. More slots give the system more flexibility to match you.</p>
                         <div class="space-y-4 mb-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-300 mb-2">Speedups</label>
                                <div class="flex gap-2 mb-2">
                                    <button type="button" data-unit="days" data-section="research" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Days</button>
                                    <button type="button" data-unit="hours" data-section="research" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Hours</button>
                                    <button type="button" data-unit="minutes" data-section="research" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gold bg-kvk-gold text-kvk-gray-900 font-bold transition">Minutes</button>
                                </div>
                                <div id="input-group-research" class="grid grid-cols-3 gap-2">
                                    <div class="hidden" id="days-container-research">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Days</label>
                                        <input type="number" id="days-research" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                    <div class="hidden" id="hours-container-research">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Hours</label>
                                        <input type="number" id="hours-research" min="0" max="23" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                    <div id="minutes-container-research">
                                        <label class="block text-[10px] uppercase text-gray-500 mb-1">Minutes</label>
                                        <input type="number" id="mins-research" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                    </div>
                                </div>
                                <input type="hidden" name="speedups-research" id="speedups-research" value="0">
                            </div>
                            <div>
                                <label for="truegold_dust" class="block text-sm font-medium text-gray-300">TrueGold Dust</label>
                                <input type="number" name="truegold_dust" id="truegold_dust" min="0" class="mt-1 block w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200">
                            </div>
                        </div>
                        <div id="slot-grid-research" class="grid grid-cols-7 gap-1 mb-4">
                            {% for i in range(slot_labels|length) %}<div class="slot" data-index="{{ i }}"><div class="slot-content">{{ slot_labels[i] }}</div></div>{% endfor %}
                        </div>
                        <input type="hidden" name="slots-research" id="slots-input-research">
                    </div>
                    {% elif day == 'training' %}
                    <div class="p-4 rounded-lg bg-kvk-gray-900 border border-kvk-gray-700">
                        <h3 class="font-bold text-xl mb-2 text-red-500">Day 4: Troop Training</h3>
                        <p class="text-xs text-gray-400 mb-4 italic">Enter resources and select <strong>all feasible</strong> time slots. More slots give the system more flexibility to match you.</p>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-300 mb-2">Speedups</label>
                            <div class="flex gap-2 mb-2">
                                <button type="button" data-unit="days" data-section="training" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Days</button>
                                <button type="button" data-unit="hours" data-section="training" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gray-700 bg-kvk-gray-700 text-gray-400 hover:bg-kvk-gray-600 transition">Hours</button>
                                <button type="button" data-unit="minutes" data-section="training" class="unit-btn flex-1 py-1 px-2 text-xs rounded border border-kvk-gold bg-kvk-gold text-kvk-gray-900 font-bold transition">Minutes</button>
                            </div>
                            <div id="input-group-training" class="grid grid-cols-3 gap-2">
                                <div class="hidden" id="days-container-training">
                                    <label class="block text-[10px] uppercase text-gray-500 mb-1">Days</label>
                                    <input type="number" id="days-training" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                </div>
                                <div class="hidden" id="hours-container-training">
                                    <label class="block text-[10px] uppercase text-gray-500 mb-1">Hours</label>
                                    <input type="number" id="hours-training" min="0" max="23" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                </div>
                                <div id="minutes-container-training">
                                    <label class="block text-[10px] uppercase text-gray-500 mb-1">Minutes</label>
                                    <input type="number" id="mins-training" min="0" placeholder="0" class="dynamic-input w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md text-gray-200 text-sm">
                                </div>
                            </div>
                            <input type="hidden" name="speedups-training" id="speedups-training" value="0">
                        </div>
                        <div id="slot-grid-training" class="grid grid-cols-7 gap-1 mb-4">
                            {% for i in range(slot_labels|length) %}<div class="slot" data-index="{{ i }}"><div class="slot-content">{{ slot_labels[i] }}</div></div>{% endfor %}
                        </div>
                        <input type="hidden" name="slots-training" id="slots-input-training">
                    </div>
                    {% endif %}
                {% endfor %}
            </div>
```

- [ ] **Step 2: Run pytest to check existing tests**

Run: `./venv/bin/pytest`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add app/templates/player_form.html
git commit -m "feat: render player form day cards in active_days order"
```

---

### Task 4: Integration Tests for Chronological Day Ordering & Full Suite Verification

**Files:**
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Write integration tests in `tests/test_routes.py`**

Add tests for:
1. `player_form` with Day 2 research has Research card HTML before Training card HTML.
2. `player_form` with Day 5 research has Training card HTML before Research card HTML.
3. `admin_dashboard` with Day 2 research has Tab Research before Tab Training.
4. `admin_dashboard` with Day 5 research has Tab Training before Tab Research.
5. `locked_appointments` with Day 2 research has Tab Research before Tab Training.
6. `public_schedule` with Day 2 research has Research schedule before Training schedule.

```python
def test_player_form_chronological_ordering_day_2(client):
    # Create event with research_day = 2
    resp = client.post(
        "/create",
        data={
            "event_name": "Day 2 Event",
            "research_day": "2",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    event_uid = resp.location.split("/success/")[1].split("?")[0]

    # Fetch player form
    form_resp = client.get(f"/event/{event_uid}")
    assert form_resp.status_code == 200
    html = form_resp.get_data(as_text=True)

    # Verify order in HTML: Day 1: Construction -> Day 2: Research -> Day 4: Troop Training
    pos_const = html.find("Day 1: Construction")
    pos_research = html.find("Day 2: Research")
    pos_training = html.find("Day 4: Troop Training")

    assert pos_const != -1
    assert pos_research != -1
    assert pos_training != -1
    assert pos_const < pos_research < pos_training


def test_player_form_chronological_ordering_day_5(client):
    # Create event with research_day = 5
    resp = client.post(
        "/create",
        data={
            "event_name": "Day 5 Event",
            "research_day": "5",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    event_uid = resp.location.split("/success/")[1].split("?")[0]

    # Fetch player form
    form_resp = client.get(f"/event/{event_uid}")
    assert form_resp.status_code == 200
    html = form_resp.get_data(as_text=True)

    # Verify order in HTML: Day 1: Construction -> Day 4: Troop Training -> Day 5: Research
    pos_const = html.find("Day 1: Construction")
    pos_training = html.find("Day 4: Troop Training")
    pos_research = html.find("Day 5: Research")

    assert pos_const != -1
    assert pos_training != -1
    assert pos_research != -1
    assert pos_const < pos_training < pos_research


def test_admin_dashboard_chronological_ordering(client, app):
    # Create event with research_day = 2
    resp = client.post(
        "/create",
        data={
            "event_name": "Day 2 Admin Event",
            "research_day": "2",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    event_uid = resp.location.split("/success/")[1].split("?")[0]
    secret = resp.location.split("secret=")[1]

    # Fetch admin dashboard
    admin_resp = client.get(f"/event/{event_uid}/admin/{secret}")
    assert admin_resp.status_code == 200
    html = admin_resp.get_data(as_text=True)

    # Verify tab button order in nav
    pos_tab_const = html.find('data-target="tab-construction"')
    pos_tab_research = html.find('data-target="tab-research"')
    pos_tab_training = html.find('data-target="tab-training"')

    assert pos_tab_const != -1
    assert pos_tab_research != -1
    assert pos_tab_training != -1
    assert pos_tab_const < pos_tab_research < pos_tab_training


def test_locked_and_public_schedule_chronological_ordering(client):
    # Create event with research_day = 2
    resp = client.post(
        "/create",
        data={
            "event_name": "Day 2 Schedule Event",
            "research_day": "2",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    event_uid = resp.location.split("/success/")[1].split("?")[0]

    # Finalized schedule
    fin_resp = client.get(f"/event/{event_uid}/finalized")
    assert fin_resp.status_code == 200
    fin_html = fin_resp.get_data(as_text=True)
    pos_fin_const = fin_html.find('data-target="tab-construction"')
    pos_fin_research = fin_html.find('data-target="tab-research"')
    pos_fin_training = fin_html.find('data-target="tab-training"')
    assert pos_fin_const < pos_fin_research < pos_fin_training

    # Public schedule
    pub_resp = client.get(f"/event/{event_uid}/schedule")
    assert pub_resp.status_code == 200
    pub_html = pub_resp.get_data(as_text=True)
    pos_pub_const = pub_html.find("Construction Schedule")
    pos_pub_research = pub_html.find("Research (Day 2) Schedule")
    pos_pub_training = pub_html.find("Training Schedule")
    assert pos_pub_const < pos_pub_research < pos_pub_training
```

- [ ] **Step 2: Run pytest to verify all tests pass**

Run: `./venv/bin/pytest`
Expected: All tests pass.

- [ ] **Step 3: Run ruff checks and formatting**

Run:
```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
```
Expected: All checks pass!

- [ ] **Step 4: Commit**

```bash
git add tests/test_routes.py
git commit -m "test: add integration tests for chronological day ordering"
```
