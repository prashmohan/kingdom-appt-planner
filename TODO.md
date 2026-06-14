# TODO: KingShot KvK Appointment Planner Improvements & Fixes

This document outlines the bugs, security vulnerabilities, performance bottlenecks, and architectural tech debt discovered during the code review, along with actionable steps to address them.

---

## 🐛 1. Bugs & Robustness Issues

### [ ] 1.1 Prevent Crash in Distribution Algorithm on Invalid Slot Indices (KeyError)
* **Location:** [logic.py](file:///home/prmohan/projects/kvk-appt/app/logic.py#L116)
* **Challenge:** The `slot_demand` dictionary is initialized with keys from `0` to `48`. If a player submits a slot index outside this range (e.g., `-1` or `50`), the list comprehension `available_feasible` retains it, and the `min()` function tries to look up `slot_demand[s]`, raising a `KeyError` and crashing the entire distribution process.
* **Remediation:** Filter `feasible_slots` to ensure only indices within `range(49)` are processed:
  ```python
  feasible_slots = [s for s in feasible_slots if isinstance(s, int) and 0 <= s < 49]
  ```

### [ ] 1.2 Prevent Crash in Distribution Algorithm on Non-List Slot Input (TypeError)
* **Location:** [logic.py](file:///home/prmohan/projects/kvk-appt/app/logic.py#L110)
* **Challenge:** If a user bypasses client-side validation and sends a value that parses as a valid JSON type but is not iterable (e.g., `"123"` parses as integer `123`), the database stores it. When the algorithm runs, `for s in feasible_slots` throws a `TypeError: 'int' object is not iterable` which is uncaught, crashing the request.
* **Remediation:** Check that the parsed `feasible_slots` is indeed a list:
  ```python
  if not isinstance(feasible_slots, list):
      # Handle as invalid
  ```

### [ ] 1.3 Safely Split `submission_id` in Admin Operations
* **Locations:**
  * `/admin/<event_uid>/delete` in [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L946)
  * `/admin/<event_uid>/manual_assign` in [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L745)
  * `/admin/<event_uid>/unset` in [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L1003)
* **Challenge:** Splitting `submission_id` directly with `submission_id.split("_", 2)` assumes it always contains exactly three parts separated by two underscores. If the ID is malformed or manipulated, this will raise a `ValueError` and return a `500 Internal Server Error`.
* **Remediation:** Wrap the split in a try-catch block or validate the parts before unpacking:
  ```python
  parts = submission_id.split("_", 2)
  if len(parts) != 3:
      return "Invalid Submission ID", 400
  _, player_id, day_type = parts
  ```

### [ ] 1.4 Fix Inconsistency in Public Schedule URL
* **Locations:** 
  * `/event/<event_uid>/schedule` in [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L682)
  * [public_schedule.html](file:///home/prmohan/projects/kvk-appt/app/templates/public_schedule.html#L88)
* **Challenge:** The public schedule endpoint fetches assignments directly from the `assignments` table but does not join with the `submissions` table. As a result, it displays numeric player IDs (e.g., `12345678`) on the schedule page. This is a severe UX bug, as users expect to see player names and alliances.
* **Remediation:** Update the SQL query in the `/event/<event_uid>/schedule` route to join `assignments` with `submissions` (similar to `/event/<event_uid>/finalized`) and render player nicknames and alliance tags. Alternatively, redirect `/event/<event_uid>/schedule` to `/event/<event_uid>/finalized` and deprecate `public_schedule.html` to eliminate code redundancy.

---

## 🛡️ 2. Security Vulnerabilities

### [ ] 2.1 Persist Backpack Screenshots (Prevent Ephemeral Storage Loss)
* **Location:** [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L369)
* **Challenge:** Uploaded backpack screenshots are stored in `/app/app/static/uploads`. In the Docker configuration, only `/app/data` is mapped to a persistent volume. This means all uploaded verification images are stored on the ephemeral container filesystem and will be permanently lost whenever the container is updated or restarted.
* **Remediation:** Change the upload directory to `/app/data/uploads` (which is inside the persistent volume) and implement a custom Flask route to serve these files, or configure a symbolic link from the static folder to the data folder during container entrypoint.

### [ ] 2.2 Persist Audit Log Files
* **Location:** [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L95)
* **Challenge:** The audit log directory is configured at `os.path.join(app.root_path, "..", "logs")` which translates to `/logs` inside the Docker container. This directory is not mounted as a volume, meaning all admin audit trails disappear on container restart.
* **Remediation:** Modify the log path to write to `/app/data/logs/audit.log` so it is automatically persisted inside the SQLite data volume.

### [ ] 2.3 Move Hardcoded API Secret to Environment Variables
* **Location:** [config.py](file:///home/prmohan/projects/kvk-appt/config.py#L14)
* **Challenge:** The `EXTERNAL_API_SECRET` (`"mN4!pQs6JrYwV9"`) used to generate signatures for the third-party game API is hardcoded directly in the python configuration. If this secret is compromised or changes, it requires a code deploy.
* **Remediation:** Load the secret from the environment with a default only for development:
  ```python
  EXTERNAL_API_SECRET = os.environ.get("EXTERNAL_API_SECRET", "mN4!pQs6JrYwV9")
  ```

### [ ] 2.4 Enforce SQLite Foreign Keys
* **Location:** [database.py](file:///home/prmohan/projects/kvk-appt/app/database.py#L8)
* **Challenge:** SQLite does not enforce foreign keys by default, even if they are defined in table schemas. They must be explicitly enabled per connection. Currently, a deleted event would leave orphan submissions and assignments in the database because foreign key cascades/checks are disabled.
* **Remediation:** Add `db.execute("PRAGMA foreign_keys = ON")` to the connection setup in `get_db()`.

### [ ] 2.5 Tighten Content Security Policy (CSP)
* **Location:** [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L123)
* **Challenge:** The Content Security Policy header uses `'unsafe-inline'` for `script-src` and `style-src` because pages contain inline scripts (Tailwind configuration, UI behaviors). This drastically reduces the protection CSP offers against Cross-Site Scripting (XSS).
* **Remediation:** Extract inline styles and scripts into static files and remove `'unsafe-inline'` from the CSP headers.

---

## ⚡ 3. Performance & Scalability Issues

### [ ] 3.1 Avoid Blocking Flask Workers During Player Data Refresh
* **Location:** [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L178)
* **Challenge:** Clicking "Refresh Player Data" in the admin dashboard runs a loop that sequentially triggers synchronous `requests.post()` calls for each unique player. A KvK event with 100+ players will block the single Flask worker thread for up to several minutes. If all WSGI worker processes are blocked this way, the app will become completely unresponsive to other users (self-inflicted DoS).
* **Remediation:** 
  1. Use `concurrent.futures.ThreadPoolExecutor` to fetch player data concurrently in batches.
  2. Implement an asynchronous task worker (e.g. running in a background thread or Celery task) and use a WebSocket or AJAX polling mechanism to display progress, rather than doing it inside the request lifecycle.

### [ ] 3.2 Add Missing Database Indexes
* **Location:** [database.py](file:///home/prmohan/projects/kvk-appt/app/database.py#L17)
* **Challenge:** Submissions and assignments tables are frequently queried by `event_uid` and `player_id` but have no indexes on these columns. As the data grows across multiple events, every schedule load or submission edit will trigger full table scans.
* **Remediation:** Add indexes on search keys during database initialization:
  ```sql
  CREATE INDEX IF NOT EXISTS idx_submissions_event_uid ON submissions(event_uid);
  CREATE INDEX IF NOT EXISTS idx_submissions_player ON submissions(event_uid, player_id);
  CREATE INDEX IF NOT EXISTS idx_assignments_event_uid ON assignments(event_uid);
  ```

---

## 🛠️ 4. Technical Debt, DRY & Best Practices

### [ ] 4.1 Transition Away from Ad-Hoc Startup Schema Migrations
* **Location:** [database.py](file:///home/prmohan/projects/kvk-appt/app/database.py#L53)
* **Challenge:** Column presence checks and table migrations (e.g., `PRAGMA table_info` followed by `ALTER TABLE submissions ADD COLUMN`) are done inside the application connection path on every startup. Running this concurrently across multiple Gunicorn workers can result in table locks or race conditions.
* **Remediation:** Use a proper schema migration manager (e.g. Alembic/Flask-Migrate) or isolate schema initializations/migrations into a separate bootstrap command run before WSGI workers spawn.

### [ ] 4.2 Dry-Up Templates Using a Base Template (`base.html`)
* **Location:** [templates/](file:///home/prmohan/projects/kvk-appt/app/templates)
* **Challenge:** There is no layout inheritance. Boilerplate HTML structure, Tailwind CDN tags, and style sheets are copied verbatim across all 9 HTML templates. Maintaining a consistent design system or making global aesthetic updates is extremely difficult.
* **Remediation:** Create a `base.html` template containing the head configuration, core styling, and imports. Refactor all other templates to extend `base.html` and define block overrides.

### [ ] 4.3 Add Fallback Nickname Inputs for Game API Outages
* **Location:** [player_form.html](file:///home/prmohan/projects/kvk-appt/app/templates/player_form.html#L384) & [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L350)
* **Challenge:** The form forces player validation via the external `kingshot-giftcode` API. If that API goes down or changes its signing signature, users cannot register because the name cannot be fetched, and the form submission is rejected.
* **Remediation:** Introduce a fallback mechanism. If the automated name fetch fails or times out, display a text field allowing the player to manually enter their nickname, and log a warning.

### [ ] 4.4 Upgrade Docker Compose Configuration
* **Location:** [docker-compose.yml](file:///home/prmohan/projects/kvk-appt/docker-compose.yml#L1)
* **Challenge:** The file declares version `2.4` which is outdated.
* **Remediation:** Upgrade to version `3.8` (or remove the version field entirely to match modern compose standards) to ensure compatibility with modern container runtimes.

### [ ] 4.5 Standardize Exception Logging
* **Location:** [__init__.py](file:///home/prmohan/projects/kvk-appt/app/__init__.py#L83)
* **Challenge:** The code contains multiple generic `except Exception: pass` statements (e.g., in `fetch_player_info`). This silences connection failures, DNS errors, or API contract changes, making them impossible to diagnose.
* **Remediation:** Log caught exceptions using the app logger at `error` or `warning` level so they appear in logs.
