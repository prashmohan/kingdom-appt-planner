# Drawer Assign Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Assign" button to the player detail drawer in the admin dashboard to streamline manual assignments using AJAX and confirmation prompts.

**Architecture:** 
- Update backend to include `submission_id` in `slot_players` data.
- Update frontend to expose current assignments to JavaScript.
- Add an "Assign" button to the drawer UI with conflict detection logic.
- Reuse existing AJAX refresh logic for a seamless experience.

**Tech Stack:** Python (Flask), Jinja2, JavaScript (Vanilla), Tailwind CSS.

---

### Task 1: Backend Data Enhancement

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_routes.py`

- [ ] **Step 1: Update slot_players dictionary**
  - In the `admin_dashboard` route, add `"submission_id": sub["id"]` to the objects appended to `slot_players[day][slot_index]`.

- [ ] **Step 2: Update existing test**
  - Update `test_heatmap_hover_potential_players` to verify that the returned data structure (if checked via manual inspection or small unit test) now contains the ID.
  - Or add a new unit test for the `slot_players` structure if a suitable route exists (can just check the `render_template` call if using a mock).

- [ ] **Step 3: Commit**
```bash
git add app/__init__.py tests/test_routes.py
git commit -m "feat: include submission_id in slot_players data for drawer assignment"
```

### Task 2: Frontend Data Exposure and Drawer UI

**Files:**
- Modify: `app/templates/admin_dashboard.html`

- [ ] **Step 1: Expose current assignments to JS**
  - Inside the `{% for day in active_days %}` loop, update the script block to also store `window.currentAssignments['{{ day }}'] = {{ assignments[day]|tojson }};`.

- [ ] **Step 2: Update drawer content template**
  - Modify the `selectSlot` function's template literal to include an "Assign" button for each player.
  - The button should have a `data-submission-id` and `data-player-name` attribute.
  - Add an `onclick` that calls `assignFromDrawer('{{ day }}', ${index}, '${p.submission_id}', '${p.player_name}')`.
  - Style the button using Tailwind (e.g., `bg-blue-600 text-white px-2 py-1 rounded text-[10px]`).

- [ ] **Step 3: Commit**
```bash
git add app/templates/admin_dashboard.html
git commit -m "feat: expose assignments to JS and add Assign button to drawer"
```

### Task 3: Implementation of Assignment Logic

**Files:**
- Modify: `app/templates/admin_dashboard.html`

- [ ] **Step 1: Create a hidden assignment form**
  - Add a hidden form in the template that will be used to trigger the `manual_assign` action.
  - It needs fields for `submission_id`, `slot_index`, `secret`, and `csrf_token`.

- [ ] **Step 2: Implement assignFromDrawer function**
  - Add the function to the main script block.
  - Logic:
    1. Check if `window.currentAssignments[day][slotIndex]` exists.
    2. If yes, get the current player's name.
    3. `confirm(`This slot is already assigned to ${currentName}. Replace with ${newName}?`)`.
    4. If no conflict or confirmed, populate the hidden form and call `handleFormSubmit({ target: hiddenForm, preventDefault: () => {} })` or similar to trigger the AJAX flow.

- [ ] **Step 3: Commit**
```bash
git add app/templates/admin_dashboard.html
git commit -m "feat: implement AJAX assignment logic with conflict detection"
```

### Task 4: Final Verification and Polish

- [ ] **Step 1: Manual Verification**
  - Verify tapping a slot updates the drawer.
  - Verify clicking "Assign" works for an empty slot.
  - Verify clicking "Assign" for an occupied slot shows the confirmation prompt.
  - Verify the heatmap updates immediately after assignment without reload.

- [ ] **Step 2: Run all tests**
```bash
pytest
```

- [ ] **Step 3: Final Commit**
```bash
git commit -m "docs: complete drawer assignment button implementation"
```
