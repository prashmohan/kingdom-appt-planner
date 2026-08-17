# Technical Design Specification: Superadmin Interface & Global Analytics

**Date:** 2026-08-17  
**Status:** Approved  
**Author:** AI Pair Programmer & Prash Mohan  

---

## 1. Overview & Objectives

The **Kingdom Appointment Planner** coordinates player time slots for time-limited "King's Buffs" across individual events (kingdoms). Currently, administrators only have access to their individual event dashboards via their secret link (`/admin/<event_uid>?secret=<admin_secret>`).

This feature introduces a dedicated **Superadmin Interface** restricted exclusively to the platform operator. It provides:
1. **Global KPIs & Usage Statistics:** Aggregated metrics across all registered events (total events, submissions, unique players, fill rates, lock rates, resource commitments, and buff type distributions).
2. **Time-Frame Filtering:** Dynamic time-range scoping (`1w`, `2w`, `4w`, and `all`).
3. **Popular Events & Insights Spotlight:** Leaderboard of top kingdoms by participation, superlatives (most contested, highest resources), and peak demand UTC time slots.
4. **Interactive Registered Events Registry Table:** Comprehensive table listing every event, its status, metrics, and direct 1-click access to its individual `/admin/<event_uid>?secret=<admin_secret>` dashboard.

---

## 2. Security & Authentication Architecture

### 2.1 Configuration
* Add `SUPERADMIN_SECRET` to `config.py` (read from `os.environ.get("SUPERADMIN_SECRET", "dev-superadmin-secret-change-me")`).
* Add `"superadmin"` to `RESERVED_SLUGS` in `app/logic.py` to prevent conflicts with custom event slugs.

### 2.2 Access Control & Session Persistence
* **Entry URL (`/superadmin`):**
  * When a request arrives at `GET /superadmin`:
    * If `request.args.get("secret") == Config.SUPERADMIN_SECRET`:
      * Set `session["is_superadmin"] = True`.
      * Redirect (302) to `url_for("superadmin", range=request.args.get("range", "all"))` to clean the URL parameter from the address bar and browser history.
    * Else if `session.get("is_superadmin") is True`:
      * User is authenticated; proceed to process request and render dashboard.
    * Else:
      * Reject request immediately with `403 Forbidden`. No event metadata or dashboard structure is leaked.
* **Logout Endpoint (`/superadmin/logout`):**
  * Pops `is_superadmin` from the Flask session.
  * Redirects to `/`.

---

## 3. Data Processing & Analytics Engine

### 3.1 Time-Frame Filter
The query parameter `range` (`1w`, `2w`, `4w`, `all`, default `all`) sets the filter boundary on `events.created_at`:
* `1w`: `created_at >= datetime('now', '-7 days')`
* `2w`: `created_at >= datetime('now', '-14 days')`
* `4w`: `created_at >= datetime('now', '-28 days')`
* `all`: No date restriction

### 3.2 Metrics Computation Helper (`app/logic.py` / `get_superadmin_metrics`)
A dedicated pure/database-backed helper function `get_superadmin_metrics(db, time_range='all')` computes:

1. **Global KPIs**:
   * `total_events`: Count of registered events within the time frame.
   * `total_submissions`: Overall count of player submissions.
   * `total_unique_players`: Count of distinct `player_id` across submissions.
   * `total_alliances`: Count of distinct `alliance_name` entries.
   * `total_assigned_slots`: Total number of slots filled across all events.
   * `total_locked_slots`: Total number of slots locked by event admins.
   * `global_fill_rate`: `(total_assigned_slots / total_capacity_slots) * 100` (where total capacity is sum of `slot_count * active_days_count` per event).
   * `global_lock_rate`: `(total_locked_slots / total_assigned_slots) * 100` (if assigned > 0).
   * `total_resources_pledged`: Sum of calculated resources across all submissions.
   * `avg_submissions_per_event`: `total_submissions / total_events` (if events > 0).

2. **Buff Type Breakdown**:
   * Submissions and assignments grouped by `construction`, `training`, and `research`.

3. **Peak Time Slots (UTC)**:
   * Aggregation across all submissions' `feasible_slots` to identify top 3 requested 30-minute intervals across kingdoms.

4. **Popular Events Leaderboard & Superlatives**:
   * Top 5 events ranked by submission volume.
   * **Most Contested Kingdom**: Event with the highest ratio of submissions to total available slots.
   * **Top Resource Kingdom**: Event with the highest sum of resources pledged.

5. **Detailed Event List for Table**:
   * List of dictionaries for each event containing:
     * `uid`, `name`, `created_at`, `active_days` (parsed list), `slot_count`, `admin_secret`
     * `admin_url`: Direct URL to `/admin/<uid>?secret=<admin_secret>`
     * `public_url`: Direct URL to `/schedule/<uid>`
     * `player_url`: Direct URL to `/player/<uid>`
     * `submission_count`, `unique_player_count`, `assigned_slot_count`, `locked_slot_count`
     * `fill_percentage`: Percentage of slots allocated for this specific event.

---

## 4. User Interface Specification (`app/templates/superadmin.html`)

### 4.1 Visual Design & Structure
Consistent with the dark theme (`bg-kvk-gray-900`, `kvk-gold`, `kvk-blue`):

1. **Header & Navigation Bar**:
   * Title: `👑 Superadmin Console`.
   * Time filter button group (`1 Week`, `2 Weeks`, `4 Weeks`, `All Time`) with active state styling.
   * Logout button (`/superadmin/logout`).

2. **Overview KPI Cards (Grid of 4)**:
   * Total Events Registered
   * Total Submissions
   * Unique Players
   * Global Slot Fill & Confirmation Rate

3. **Analytics & Highlights Grid (3 Columns / Cards)**:
   * **Buff Distribution Card**: Visual progress bars showing Construction vs. Training vs. Research volume.
   * **Popular Events Superlatives**: Badges/cards for Most Contested Event and Highest Resource Event, plus Top 5 active events.
   * **Peak UTC Demand Hours**: Top requested time intervals globally.

4. **Registered Events Table**:
   * **Search Input**: Instant client-side filtering by Event Name or UID.
   * **Table Columns**:
     * Event Name (with link to Public Schedule)
     * UID / Slug
     * Created Date (formatted UTC)
     * Active Days (badges)
     * Submissions Count
     * Unique Players Count
     * Slot Fill Progress (e.g. `42/49 (85%)`)
     * Actions:
       * Primary "Open Admin" button (links to `/admin/<uid>?secret=<admin_secret>`)
       * "Copy Link" button with clipboard toast
       * Player form link

---

## 5. Error Handling & Edge Cases

* **No events in selected time range**: Dashboard displays graceful empty-state placeholders with 0 values rather than division-by-zero or template rendering errors.
* **Corrupted or missing `raw_data` / `feasible_slots` in legacy submissions**: Fall back safely without crashing JSON parsing.
* **Missing or default `SUPERADMIN_SECRET`**: Generates warning in log if secret is unchanged from default.
* **Unauthorized access attempts**: Return 403 Forbidden with zero sensitive information in response body.

---

## 6. Testing & Quality Assurance Plan

1. **Unit & Logic Tests (`tests/test_logic.py`)**:
   * Test `get_superadmin_metrics` with sample database data across all time filters (`1w`, `2w`, `4w`, `all`).
   * Verify division-by-zero safety when no events exist.
   * Verify correct aggregation of unique players and slot fill rates.
   * Verify `"superadmin"` is rejected as a custom slug.

2. **Route & Security Tests (`tests/test_routes.py`)**:
   * Unauthorized access to `/superadmin` without secret or session returns 403.
   * Access with valid `?secret=<SUPERADMIN_SECRET>` sets session, redirects cleanly to `/superadmin`, and renders 200 OK.
   * Event admin secret passed to `/superadmin` is rejected with 403.
   * Session persistence allows subsequent `/superadmin?range=1w` requests without re-passing the secret.
   * `/superadmin/logout` clears session and restricts subsequent access.
   * Direct admin links in the registered events table correctly embed the individual event's `admin_secret`.

3. **Linting & Code Quality**:
   * Pass `./venv/bin/ruff check .`
   * Pass `./venv/bin/ruff format --check .`
   * All pytest tests pass (`./venv/bin/pytest`).
