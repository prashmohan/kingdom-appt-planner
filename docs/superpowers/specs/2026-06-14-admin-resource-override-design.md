# Specification: Admin Resource Override Feature

This document outlines the design and specification for adding resource override capabilities directly from the Admin Dashboard in the Kingdom Appointment Planner.

## 1. Objective & Background

Currently, player submissions are viewed on the admin page, but overriding them requires the player to submit another form or direct DB manipulation. Admins need a direct way to override resources (speedups, truegold, truegold dust, etc.) and have the system automatically recalculate the player's score and update the schedules/tables inline.

## 2. Requirements & UX

* **Row Click Trigger:** Clicking anywhere on a player's submission row (excluding interactive inputs/buttons/forms) will toggle an inline expandable shelf directly below that row.
* **Inline Shelf Design:** Matches the dashboard aesthetic (dark backgrounds, borders, and gold accents).
* **Dynamic Inputs:** Displays only relevant fields based on the type of submission:
  * **Construction:** Speedups (minutes), Truegold, Tempered Truegold.
  * **Training:** Speedups (minutes).
  * **Research:** Speedups (minutes), Truegold Dust.
* **Backend Recalculation:** Submitting updates will invoke a backend controller to save the raw resource numbers, recalculate the score (resources), update the database, and audit log the action.
* **AJAX Inline Update:** Saving values utilizes the existing dashboard AJAX pipeline for seamless, non-reloading updates.

## 3. Architecture & Data Flow

### 3.1 Backend Updates (`app/__init__.py`)

1. **Dashboard Route Data Processing:**
   * Modify the `admin_dashboard` route to deserialize `raw_data` JSON to a new attribute on each submission (`sub["raw_resources"]`) before passing it to the Jinja2 context.

2. **New POST Route (`/admin/<event_uid>/override_resources`):**
   * Verifies the event and the admin `secret`.
   * Accepts `submission_id` and the raw resource inputs.
   * Recalculates the score:
     * **Construction:** `score = (speedups * 30) + (truegold * 2000) + (tempered_truegold * 30000)`
     * **Training:** `score = speedups * 90`
     * **Research:** `score = (speedups * 30) + (truegold_dust * 1000)`
   * Updates `raw_data` and `resources` fields in the `submissions` table.
   * Logs an audit entry: `ADMIN: Override resources for submission {submission_id} (day_type={day_type}) - score={score}, raw_data={raw_data} in event {event_uid}`.
   * Redirects to the admin dashboard.

### 3.2 HTML/Template Updates (`app/templates/admin_dashboard.html`)

1. **Submission Table Row:**
   * Add cursor/hover classes: `cursor-pointer hover:bg-kvk-gray-700/50 transition-colors`.
   * Add `onclick="toggleSubmissionShelf(event, '{{ sub.id }}')"` to the `<tr>` element.

2. **Expandable Shelf Row:**
   * Render a second `<tr>` right after the main row with `id="shelf-{{ sub.id }}"` and class `hidden`.
   * The shelf spans all columns with `<td colspan="6">` and contains the dynamic resource inputs, a Save button, and a Cancel button.

### 3.3 JavaScript Updates

* Define a new helper function:
  ```javascript
  function toggleSubmissionShelf(event, subId) {
      if (event.target.closest('input, button, select, a, form')) {
          return; // Ignore clicks on interactive elements
      }
      const shelf = document.getElementById(`shelf-${subId}`);
      if (shelf) {
          shelf.classList.toggle('hidden');
      }
  }
  ```

## 4. Test Strategy

* Write integration tests in `tests/test_routes.py` verifying:
  * Overriding resources with valid inputs successfully recalculates the score and updates the database.
  * Attempting to override resources with an invalid admin secret returns a `403 Forbidden` response.
  * Handled values default properly when inputs are missing/empty.
