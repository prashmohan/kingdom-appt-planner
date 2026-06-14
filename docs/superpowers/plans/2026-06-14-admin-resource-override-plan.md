# Implementation Plan: Admin Resource Override Feature

This plan details the steps required to implement the resource override functionality in the admin dashboard.

## Phase 1: Backend Logic Updates (`app/__init__.py`)

1. **Step 1.1: Parse Raw Resources in Dashboard Route**
   * Locate the `admin_dashboard` route.
   * Modify the submission loops to deserialize the JSON `raw_data` for each submission into a Python dictionary: `sub["raw_resources"] = json.loads(sub["raw_data"])`.

2. **Step 1.2: Implement `override_resources` POST Route**
   * Define the route `@app.route("/admin/<event_uid>/override_resources", methods=["POST"])`.
   * Implement validation of the admin secret.
   * Fetch submission by ID to determine the `day_type`.
   * Parse the incoming form parameters, defaulting to 0:
     * Construction: `speedups`, `truegold`, `tempered_truegold`
     * Training: `speedups`
     * Research: `speedups`, `truegold_dust`
   * Calculate the score based on formulas.
   * Update the `resources` and `raw_data` fields of the submission in the database.
   * Add audit logging: `app.audit_logger.info(...)`.
   * Redirect to the `admin_dashboard`.

## Phase 2: Frontend Changes (`app/templates/admin_dashboard.html`)

1. **Step 2.1: Implement JavaScript toggle function**
   * Define `toggleSubmissionShelf(event, subId)` under `<script>` inside `admin_dashboard.html`.
   * Ensure it checks `event.target.closest('input, button, select, a, form')` to prevent triggering on interactive components.

2. **Step 2.2: Add Table Styling and Click Handlers**
   * Locate the `submissions-table-{{day}}` body.
   * Add cursor pointer/hover style classes to the submission rows: `cursor-pointer hover:bg-kvk-gray-700/50 transition-colors`.
   * Add the `onclick="toggleSubmissionShelf(event, '{{ sub.id }}')"` attribute.

3. **Step 2.3: Insert Hidden Expandable Shelf Markup**
   * Insert a new `<tr>` row with `id="shelf-{{ sub.id }}"` and class `hidden` immediately after the submission `<tr>`.
   * Implement the column span (`colspan="6"`) and the edit forms for each `day_type` containing current values as inputs, a Save button, and a Cancel button.

## Phase 3: Verification & Automated Tests

1. **Step 3.1: Write Integration Tests (`tests/test_routes.py`)**
   * Add tests checking success scenarios (recalculating the score) and failure scenarios (invalid admin secret/permission checks).

2. **Step 3.2: Run Tests**
   * Run the Pytest suite to confirm all 53 original tests plus new tests pass.
