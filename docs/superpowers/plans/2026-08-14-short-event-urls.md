# Short Event URLs & Custom Slug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow creating KvK events with short 8-character Base62 alphanumeric URLs or optional custom vanity slugs (e.g. `/event/kvk-s12`), while fully preserving backward compatibility for existing 36-character UUID events.

**Architecture:** Implement `generate_short_uid` and `validate_custom_slug` in `app/logic.py`. Update the `POST /create` route in `app/__init__.py` to handle auto-generated short IDs with collision checks and validate optional custom slugs against regex, length, uniqueness, and reserved keywords. Update `app/templates/index.html` with an optional custom slug input. Add unit and integration tests covering all validation and backward compatibility scenarios.

**Tech Stack:** Python 3.12, Flask 3.x, Jinja2, Tailwind CSS, SQLite, pytest, ruff.

## Global Constraints
- Must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
- Must pass `./venv/bin/pytest`.
- Maintain 100% backward compatibility for existing events using 36-character UUIDs.

---

### Task 1: Add `generate_short_uid` and `validate_custom_slug` with Unit Tests

**Files:**
- Modify: `app/logic.py`
- Modify: `tests/test_logic.py`

**Interfaces:**
- Produces: `generate_short_uid(length: int = 8) -> str`
- Produces: `validate_custom_slug(slug: str, db: sqlite3.Connection) -> tuple[bool, str | None]`

- [ ] **Step 1: Write failing unit tests in `tests/test_logic.py`**

Add tests to `tests/test_logic.py`:
```python
import string
from app.logic import generate_short_uid, validate_custom_slug


def test_generate_short_uid_length_and_charset():
    uid1 = generate_short_uid(8)
    uid2 = generate_short_uid(8)
    assert len(uid1) == 8
    assert len(uid2) == 8
    assert uid1 != uid2
    valid_chars = set(string.ascii_letters + string.digits)
    assert all(c in valid_chars for c in uid1)


def test_validate_custom_slug_valid(app):
    with app.app_context():
        db = database.get_db()
        # Valid slugs
        for slug in ["kvk-s12", "kvk_prep", "KvkSeason10", "123-abc"]:
            is_valid, err = validate_custom_slug(slug, db)
            assert is_valid is True
            assert err is None


def test_validate_custom_slug_invalid_format(app):
    with app.app_context():
        db = database.get_db()
        # Too short (< 3)
        assert validate_custom_slug("ab", db) == (
            False,
            "Custom URL code must be between 3 and 32 characters.",
        )
        # Too long (> 32)
        assert validate_custom_slug("a" * 33, db) == (
            False,
            "Custom URL code must be between 3 and 32 characters.",
        )
        # Invalid characters (spaces, special symbols)
        assert validate_custom_slug("kvk s12", db) == (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )
        assert validate_custom_slug("kvk@s12!", db) == (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )


def test_validate_custom_slug_reserved_keyword(app):
    with app.app_context():
        db = database.get_db()
        for kw in ["admin", "create", "success", "guide", "event", "static"]:
            is_valid, err = validate_custom_slug(kw, db)
            assert is_valid is False
            assert "reserved keyword" in err


def test_validate_custom_slug_duplicate(app):
    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret) VALUES (?, ?, ?, ?)",
            ("existing-slug", "Test Event", "{}", "secret"),
        )
        db.commit()

        is_valid, err = validate_custom_slug("existing-slug", db)
        assert is_valid is False
        assert "already taken" in err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/pytest tests/test_logic.py -k "test_generate_short_uid or test_validate_custom_slug"`
Expected: FAIL (cannot import `generate_short_uid` / `validate_custom_slug`)

- [ ] **Step 3: Implement `generate_short_uid` and `validate_custom_slug` in `app/logic.py`**

In `app/logic.py`:
```python
import re
import secrets
import string

RESERVED_SLUGS = {
    "admin",
    "create",
    "distribute",
    "event",
    "export_csv",
    "guide",
    "static",
    "success",
    "confirm",
    "unlock",
    "delete",
    "manual_assign",
    "unset",
    "override_resources",
    "update_alliance",
    "favicon.ico",
}


def generate_short_uid(length: int = 8) -> str:
    """Generate a high-entropy URL-safe alphanumeric ID (Base62)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_custom_slug(slug: str, db: sqlite3.Connection) -> tuple[bool, str | None]:
    """Validate format, length, reserved keywords, and uniqueness for a custom slug."""
    if not slug or len(slug) < 3 or len(slug) > 32:
        return False, "Custom URL code must be between 3 and 32 characters."

    if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
        return (
            False,
            "Custom URL code can only contain letters, numbers, hyphens, and underscores.",
        )

    if slug.lower() in RESERVED_SLUGS:
        return (
            False,
            f"'{slug}' is a reserved keyword. Please choose a different URL code.",
        )

    row = db.execute("SELECT 1 FROM events WHERE uid = ?", (slug,)).fetchone()
    if row:
        return (
            False,
            f"URL code '{slug}' is already taken. Please choose a different one.",
        )

    return True, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/pytest tests/test_logic.py -k "test_generate_short_uid or test_validate_custom_slug"`
Expected: PASS

- [ ] **Step 5: Run linter and commit**

```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
git add app/logic.py tests/test_logic.py
git commit -m "feat: add generate_short_uid and validate_custom_slug helpers"
```

---

### Task 2: Update `/create` Route and Event Creation Form

**Files:**
- Modify: `app/__init__.py:151-185`
- Modify: `app/templates/index.html:45-48`

**Interfaces:**
- Consumes: `generate_short_uid`, `validate_custom_slug` from `app.logic`

- [ ] **Step 1: Update `/create` route in `app/__init__.py`**

In `app/__init__.py`:
1. Import `generate_short_uid`, `validate_custom_slug` from `.logic`.
2. In `create_event`:
```python
    @app.route("/create", methods=["POST"])
    def create_event():
        event_name = request.form.get("event_name", "").strip()
        if not event_name:
            event_name = "Untitled Event"

        research_day = request.form.get("research_day", "5")
        try:
            slot_count = int(request.form.get("slot_count", "49"))
            if slot_count not in [48, 49]:
                slot_count = 49
        except ValueError:
            slot_count = 49

        db = database.get_db()

        # Handle custom slug or auto-generated short UID
        custom_slug = request.form.get("custom_slug", "").strip()
        if custom_slug:
            is_valid, err_msg = validate_custom_slug(custom_slug, db)
            if not is_valid:
                return err_msg, 400
            uid = custom_slug
        else:
            # Generate unique short UID with collision check
            while True:
                candidate_uid = generate_short_uid(8)
                exists = db.execute(
                    "SELECT 1 FROM events WHERE uid = ?", (candidate_uid,)
                ).fetchone()
                if not exists:
                    uid = candidate_uid
                    break

        admin_secret = secrets.token_urlsafe(16)

        active_days = {
            "construction": True,
            "training": True,
            "research": True,
            "research_day": int(research_day),
        }

        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
            (uid, event_name, json.dumps(active_days), admin_secret, slot_count),
        )
        db.commit()

        return redirect(url_for("success", event_uid=uid, secret=admin_secret))
```

- [ ] **Step 2: Update `app/templates/index.html` to add custom slug input field**

In `app/templates/index.html`, right after the `event_name` input block:
```html
                <div class="mb-6">
                    <label for="custom_slug" class="block text-sm font-medium text-gray-300 mb-1">Custom URL Code (Optional)</label>
                    <input type="text" name="custom_slug" id="custom_slug" 
                           pattern="[a-zA-Z0-9_-]{3,32}"
                           placeholder="e.g., kvk-season-12 (leave blank for auto-generated)" 
                           class="mt-1 block w-full bg-kvk-gray-700 border-kvk-gray-700 rounded-md shadow-sm text-gray-200 focus:border-kvk-gold focus:ring focus:ring-kvk-gold focus:ring-opacity-50">
                    <p class="text-xs text-gray-500 mt-1">3-32 letters, numbers, hyphens, or underscores. Leave empty to auto-generate an 8-character short code.</p>
                </div>
```

- [ ] **Step 3: Run pytest to ensure existing tests pass**

Run: `./venv/bin/pytest`
Expected: PASS

- [ ] **Step 4: Run linter and commit**

```bash
./venv/bin/ruff check .
./venv/bin/ruff format --check .
git add app/__init__.py app/templates/index.html
git commit -m "feat: support short auto-generated UIDs and custom slugs in create_event"
```

---

### Task 3: Comprehensive Integration Tests and Full Suite Verification

**Files:**
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Add integration tests in `tests/test_routes.py`**

Add tests covering:
1. `test_create_event_auto_short_uid`: Create event without custom slug -> UID is 8 chars alphanumeric, redirects to `/success/<uid>?secret=...`.
2. `test_create_event_with_custom_slug`: Create event with valid custom slug `kvk-s12` -> UID is `kvk-s12`.
3. `test_create_event_duplicate_custom_slug`: Returns HTTP 400 with "already taken".
4. `test_create_event_invalid_custom_slug_format`: Returns HTTP 400 with format error.
5. `test_create_event_reserved_custom_slug`: Returns HTTP 400 with reserved keyword error.
6. `test_legacy_36_char_uuid_backward_compatibility`: Create an event with a 36-char UUID directly in DB and verify player form, submission, and admin dashboard work flawlessly.

```python
def test_create_event_auto_short_uid(client, app):
    resp = client.post(
        "/create",
        data={
            "event_name": "Short UID Event",
            "research_day": "5",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/success/" in resp.location
    event_uid = resp.location.split("/success/")[1].split("?")[0]
    assert len(event_uid) == 8
    assert event_uid.isalnum()


def test_create_event_with_custom_slug(client, app):
    resp = client.post(
        "/create",
        data={
            "event_name": "Custom Slug Event",
            "custom_slug": "kvk-season-12",
            "research_day": "5",
            "slot_count": "49",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    event_uid = resp.location.split("/success/")[1].split("?")[0]
    assert event_uid == "kvk-season-12"

    # Verify form loads with custom slug
    form_resp = client.get(f"/event/{event_uid}")
    assert form_resp.status_code == 200


def test_create_event_custom_slug_errors(client, app):
    # 1. Invalid characters
    resp1 = client.post(
        "/create",
        data={
            "event_name": "Invalid Slug",
            "custom_slug": "bad slug @#$",
            "research_day": "5",
        },
    )
    assert resp1.status_code == 400
    assert "letters, numbers, hyphens" in resp1.get_data(as_text=True)

    # 2. Too short
    resp2 = client.post(
        "/create",
        data={
            "event_name": "Short Slug",
            "custom_slug": "ab",
            "research_day": "5",
        },
    )
    assert resp2.status_code == 400
    assert "between 3 and 32" in resp2.get_data(as_text=True)

    # 3. Reserved keyword
    resp3 = client.post(
        "/create",
        data={
            "event_name": "Reserved Slug",
            "custom_slug": "admin",
            "research_day": "5",
        },
    )
    assert resp3.status_code == 400
    assert "reserved keyword" in resp3.get_data(as_text=True)

    # 4. Duplicate slug
    client.post(
        "/create",
        data={
            "event_name": "Original Slug Event",
            "custom_slug": "duplicate-test",
            "research_day": "5",
        },
    )
    resp4 = client.post(
        "/create",
        data={
            "event_name": "Duplicate Slug Event",
            "custom_slug": "duplicate-test",
            "research_day": "5",
        },
    )
    assert resp4.status_code == 400
    assert "already taken" in resp4.get_data(as_text=True)


def test_legacy_36_char_uuid_backward_compatibility(client, app):
    legacy_uid = "e10adc39-49ba-42e5-a68b-59d4c6d32832"
    secret = "test-secret-12345"

    with app.app_context():
        db = database.get_db()
        db.execute(
            "INSERT INTO events (uid, name, active_days, admin_secret, slot_count) VALUES (?, ?, ?, ?, ?)",
            (
                legacy_uid,
                "Legacy UUID Event",
                json.dumps(
                    {
                        "construction": True,
                        "training": True,
                        "research": True,
                        "research_day": 5,
                    }
                ),
                secret,
                49,
            ),
        )
        db.commit()

    # Verify all routes work with legacy 36-char UUID
    # 1. Player form
    resp_form = client.get(f"/event/{legacy_uid}")
    assert resp_form.status_code == 200

    # 2. Player submission
    resp_sub = client.post(
        f"/event/{legacy_uid}/submit",
        data={
            "player_id": "98765432",
            "player_name": "LegacyPlayer",
            "alliance_name": "LEGACY",
            "speedups-construction": "60",
            "slots-construction": "[1, 2]",
        },
        follow_redirects=True,
    )
    assert resp_sub.status_code == 200

    # 3. Admin dashboard
    resp_admin = client.get(f"/event/{legacy_uid}/admin/{secret}")
    assert resp_admin.status_code == 200
    assert "LegacyPlayer" in resp_admin.get_data(as_text=True)

    # 4. Finalized schedule
    resp_fin = client.get(f"/event/{legacy_uid}/finalized")
    assert resp_fin.status_code == 200
```

- [ ] **Step 2: Run pytest to verify all tests pass**

Run: `./venv/bin/pytest`
Expected: All 85+ tests pass.

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
git commit -m "test: add integration tests for short UIDs, custom slugs, and legacy UUID compatibility"
```
