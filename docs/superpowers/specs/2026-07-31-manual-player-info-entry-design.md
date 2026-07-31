# Design Spec: Manual Player Info Entry & API Lookup Removal

**Date:** 2026-07-31  
**Status:** Approved  

---

## 1. Overview & Architecture

Due to 2FA authentication requirements introduced on Century Games' player lookup endpoint, automatic retrieval of player nicknames and avatar images from Player IDs is no longer functional.

This change replaces automatic player lookup with explicit, manual entry for both **Player ID** and **Player Name** on the submission form. In addition, all obsolete external lookup backend logic, endpoints, and admin refresh features will be completely removed.

---

## 2. User Interface Changes

### 2.1 Player Submission Form (`app/templates/player_form.html`)

* **Fields**:
  * **Player ID**: `<input type="text" name="player_id" id="player_id" required pattern="\d*" inputmode="numeric" placeholder="e.g. 12345678">`
  * **Player Name**: `<input type="text" name="player_name" id="player_name" required placeholder="e.g. KingArthur">`
  * **Alliance**: `<input type="text" name="alliance_name" id="alliance_name">`
* **Removed Components**:
  * Avatar image preview (`#avatar-container`, `#player-avatar`)
  * Dynamic status indicator (`#fetch-status`)
  * Read-only player name display (`#player-name-display`)
  * Hidden `avatar_url` input field (`#avatar_url_input`)
* **Client-Side Validation (JavaScript)**:
  * Removed AJAX `blur` event listener on `player_id` that queried `/api/proxy/player`.
  * Updated form `submit` event listener to validate:
    1. `player_id` contains only digits (`/^\d+$/`).
    2. `player_name` is non-empty after trimming.
    3. At least one resource day has entries and selected time slots (existing logic).

### 2.2 Admin Dashboard (`app/templates/admin_dashboard.html`)

* Removed the **"Refresh Player Data"** button and form from the Global Actions toolbar.

---

## 3. Backend Changes (`app/__init__.py`)

* **Deleted Logic**:
  * `fetch_player_info(fid)` helper function (which made external `requests.post()` calls to `https://kingshot-giftcode.centurygame.com/api/player`).
  * `POST /api/proxy/player` route (`proxy_player`).
  * `POST /admin/<event_uid>/refresh_players` route (`refresh_players`).
* **Updated Route (`POST /event/<event_uid>/submit`)**:
  * Obtains `player_id = request.form["player_id"].strip()` and `player_name = request.form["player_name"].strip()`.
  * Validates `player_id.isdigit()` and `player_name != ""` returning 400 status on failure.
  * Sets `avatar_url = None` for new submissions inserted into the database.

---

## 4. Test Suite Changes (`tests/test_routes.py`)

* **Removed Tests**:
  * `test_proxy_player_*` (all test cases asserting response behavior of `/api/proxy/player`).
  * `test_refresh_players` (all test cases asserting behavior of `/admin/<event_uid>/refresh_players`).
* **Updated/Added Tests**:
  * `test_submit_success`: Verifies `POST /event/<event_uid>/submit` with valid `player_id` and `player_name`.
  * `test_submit_invalid_player_id`: Verifies 400 response when `player_id` is non-numeric.
  * `test_submit_missing_player_name`: Verifies 400 response when `player_name` is empty.

---

## 5. Verification Plan

1. **Automated Tests**: Run `./venv/bin/pytest` to confirm 100% test pass rate across all route, logic, and basic test suites.
2. **Code Style**: Run `./venv/bin/ruff check .` to ensure compliance with PEP 8 standards.
