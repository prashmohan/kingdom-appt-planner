# Design Specification: Chronological Research Day Ordering

## Overview
In the Kingdom Appointment Planner, an event can be configured with Research scheduled on either **Day 2** or **Day 5** (with Construction fixed on **Day 1** and Troop Training fixed on **Day 4**). 

Currently, day lists and templates default to the static order `[Construction, Training, Research]`. This results in Research Day appearing after Troop Training even when Day 2 is selected.

This specification details the changes to ensure all views (Admin Dashboard, Player Form, Finalized Schedule, and Public Schedule) order the event days chronologically based on the configured `research_day`.

---

## 1. Day Ordering Logic

### Day Number Mapping
- `construction`: Day 1
- `research`: Day `research_day` (defaults to 5 if unspecified or None; can be 2)
- `training`: Day 4

### Helper Function: `get_ordered_active_days(active_days_config)`
A reusable helper will be defined in `app/logic.py` (and imported in `app/__init__.py`):
```python
def get_ordered_active_days(active_days_config):
    """
    Returns active days sorted chronologically by day number.
    Supports active_days_config as a dict or legacy list.
    """
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

### Expected Ordering Outcomes
- When `research_day == 2`: `["construction", "research", "training"]`
- When `research_day == 5`: `["construction", "training", "research"]`
- If specific days are disabled in the config, only active days will be returned in their chronological relative order.

---

## 2. Route & View Updates

### `app/__init__.py`
1. **`player_form` Route (`GET /event/<event_uid>`)**:
   - Compute `active_days = get_ordered_active_days(event_dict["active_days"])`.
   - Pass `active_days=active_days` to `render_template("player_form.html", event=event_dict, active_days=active_days)`.
2. **`admin_dashboard` Route (`GET /event/<event_uid>/admin/<secret>`)**:
   - Replace the static list comprehension with `active_days = get_ordered_active_days(active_days_config)`.
3. **`locked_appointments` Route (`GET /event/<event_uid>/finalized`)**:
   - Replace the static list comprehension with `active_days = get_ordered_active_days(active_days_config)`.
4. **`public_schedule` Route (`GET /event/<event_uid>/schedule`)**:
   - Replace the static list comprehension with `active_days = get_ordered_active_days(active_days_config)`.

### `app/logic.py`
- In `run_distribution_algorithm`, replace the dict iteration with `active_days = get_ordered_active_days(json.loads(event["active_days"]))` when `day_type` is not specified.

---

## 3. Template Updates

### `app/templates/player_form.html`
- Update the cards container to iterate through `active_days`:
  ```jinja2
  <div class="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
      {% for day in active_days %}
          {% if day == 'construction' %}
              <!-- Day 1: Construction Card -->
              ...
          {% elif day == 'research' %}
              <!-- Day 2/5: Research Card -->
              ...
          {% elif day == 'training' %}
              <!-- Day 4: Troop Training Card -->
              ...
          {% endif %}
      {% endfor %}
  </div>
  ```
- Retain all input IDs, data attributes, unit buttons, and slot grids exactly as they are so existing JavaScript form validation and speedup calculations continue working seamlessly.

### `app/templates/admin_dashboard.html`, `locked_appointments.html`, `public_schedule.html`
- These templates already iterate over `{% for day in active_days %}`. Because `active_days` is now provided in sorted chronological order by the backend, tabs, heatmaps, alliance summaries, and submission lists will automatically render in the correct chronological order.

---

## 4. Testing & Verification

1. **Unit Tests for Helper (`tests/test_logic.py`)**:
   - Verify `get_ordered_active_days` with `research_day=2` returns `["construction", "research", "training"]`.
   - Verify `get_ordered_active_days` with `research_day=5` returns `["construction", "training", "research"]`.
   - Verify handling of legacy lists, missing keys, and inactive days.
2. **Route / Integration Tests (`tests/test_routes.py`)**:
   - Verify `GET /event/<event_uid>` with `research_day=2` renders Research before Training in the HTML DOM order.
   - Verify `GET /event/<event_uid>` with `research_day=5` renders Training before Research.
   - Verify `GET /event/<event_uid>/admin/<secret>` with `research_day=2` renders tabs and tab content in order `[construction, research, training]`.
   - Verify `GET /event/<event_uid>/finalized` and `GET /event/<event_uid>/schedule` render in order.
3. **Full Test Suite & Linting**:
   - Run `pytest` and confirm all tests pass.
   - Run `ruff check .` and `ruff format --check .` to ensure compliance.
