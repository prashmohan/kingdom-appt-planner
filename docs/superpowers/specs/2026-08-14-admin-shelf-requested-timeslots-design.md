# Design Specification: Admin Submission Shelf Requested Timeslots

## Overview
In the Admin Dashboard (`admin_dashboard.html`), clicking on a player submission row expands an accordion "shelf" (`shelf-{{ sub.id }}`) that shows the submitted resource details and allows resource overrides.

This feature adds a clear, scannable **Requested Timeslots** badge/pill section inside this shelf so administrators can immediately see all the timeslots a player selected when submitting their entry.

---

## 1. Backend Data Flow

### `app/__init__.py` (inside `admin_dashboard` route)
When processing each submission `sub` in `submissions_by_day[day]`:
- In addition to `sub["requested_slots_text"]` (comma-separated string), also attach:
  - `sub["requested_slots_labels"]`: `list[str]` of human-readable slot labels (e.g. `["00:00", "00:30", "01:00"]`).
- If `feasible_slots` is empty, invalid, or fails to parse:
  - `sub["requested_slots_labels"] = []`
  - `sub["requested_slots_text"] = "No slots selected"` (or `"Error parsing slots"`)

```python
feasible_slots = json.loads(sub["feasible_slots"])
requested_labels = [slot_labels[i] for i in feasible_slots if 0 <= i < slot_count]
sub["requested_slots_labels"] = requested_labels
sub["requested_slots_text"] = (
    ", ".join(requested_labels) if requested_labels else "No slots selected"
)
```

---

## 2. Frontend Template Updates

### `app/templates/admin_dashboard.html`
Inside the `<tr id="shelf-{{ sub.id }}">` shelf container, above the resource override `<form>`:
```jinja2
<div class="mb-4 pb-4 border-b border-kvk-gray-700">
    <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-bold text-gray-400 uppercase tracking-wider">
            Requested Timeslots ({{ sub.requested_slots_labels|length }})
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

---

## 3. Testing & Verification

1. **Integration Tests (`tests/test_routes.py`)**:
   - Create an event and submit a player entry with specific slot indices (e.g. `[0, 1, 2]`).
   - Request the admin dashboard route (`GET /event/<event_uid>/admin/<secret>`).
   - Verify that the shelf `<tr id="shelf-...">` contains the "Requested Timeslots" header, count `(3)`, and the corresponding slot labels rendered as badge spans.
   - Verify an empty/no-slot submission renders "No timeslots selected."
2. **Full Test Suite & Linting**:
   - Run `pytest` and confirm all 78+ tests pass.
   - Run `ruff check .` and `ruff format --check .` to ensure compliance.
