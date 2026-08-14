# Design Specification: Short Event URLs & Custom Slug Support

## Overview
Currently, new KvK events generate a 36-character UUID (`str(uuid.uuid4())`) for their unique identifier (`events.uid`). While functionally robust, these long URLs are unwieldy to copy, paste, and share in mobile games or Discord channels.

This specification introduces short 8-character auto-generated URL identifiers for new events and adds support for optional custom vanity URL slugs (e.g. `/event/kvk-s12`), while guaranteeing 100% backward compatibility for all existing events with UUID identifiers.

---

## 1. Identifier Generation & Validation Logic

### Auto-Generated Short UID: `generate_short_uid(length=8)`
Defined in `app/logic.py`:
- Uses Python `secrets.choice(string.ascii_letters + string.digits)` (Base62).
- $62^8 \approx 2.18 \times 10^{14}$ unique combinations.
- Generates an 8-character alphanumeric string (e.g., `k8mX2p9Q`).

### Custom Slug Validation: `validate_custom_slug(slug, db)`
- **Format**: 3 to 32 characters, regex `^[a-zA-Z0-9_-]{3,32}$`.
- **Reserved Keywords**: `{"guide", "create", "success", "admin", "event", "static", "favicon.ico", "distribute", "export_csv", "confirm", "unlock", "delete", "manual_assign", "unset", "override_resources", "update_alliance"}`.
- **Uniqueness Check**: Queries `SELECT 1 FROM events WHERE uid = ?`.

Returns `(is_valid: bool, error_message: str | None)`.

### Admin Secret
- Generate using `secrets.token_urlsafe(16)` (22 characters, URL-safe base64, cryptographically secure).

---

## 2. Route & Controller Updates

### Event Creation: `POST /create` (`app/__init__.py`)
1. Read `custom_slug = request.form.get("custom_slug", "").strip()`.
2. If `custom_slug` is provided:
   - Run `validate_custom_slug(custom_slug, db)`.
   - If invalid/duplicate/reserved, return an HTTP 400 error with descriptive message.
   - Set `uid = custom_slug`.
3. If `custom_slug` is empty/omitted:
   - Loop `uid = generate_short_uid(8)` until `SELECT 1 FROM events WHERE uid = ?` finds no match (collision-proof).
4. Set `admin_secret = secrets.token_urlsafe(16)`.
5. Insert into `events` table and redirect to `/success/<uid>?secret=<admin_secret>`.

---

## 3. Template Updates

### `app/templates/index.html`
Add the optional custom slug input in the event creation form right below Event Name:
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

---

## 4. Backward Compatibility Guarantee
- The SQLite `events.uid` column is `TEXT UNIQUE`.
- All routes continue to query `WHERE uid = ?`.
- Existing events created with 36-character UUIDs (e.g. `e10adc39-49ba-42e5-a68b-59d4c6d32832`) continue to work without any schema migrations or data adjustments.

---

## 5. Testing & Verification

1. **Unit Tests (`tests/test_logic.py`)**:
   - `test_generate_short_uid_length_and_charset`: Verify 8-character length and alphanumeric character set.
   - `test_validate_custom_slug_valid`: Valid slugs (e.g. `kvk-s12`, `KVK_100`, `abc`).
   - `test_validate_custom_slug_invalid_format`: Invalid chars (spaces, `@`, `<3`, `>32`).
   - `test_validate_custom_slug_reserved_word`: Reserved keywords (e.g. `admin`, `create`).
   - `test_validate_custom_slug_duplicate`: Duplicate slugs already in the database.
2. **Integration Tests (`tests/test_routes.py`)**:
   - `test_create_event_auto_generated_short_uid`: Create event without custom slug, verify `uid` length is 8 and alphanumeric.
   - `test_create_event_with_custom_slug`: Create event with valid custom slug `kvk-alpha-1`, verify URLs work.
   - `test_create_event_duplicate_custom_slug_error`: Create event with existing slug, verify HTTP 400 error.
   - `test_create_event_invalid_custom_slug_error`: Create event with invalid chars, verify HTTP 400 error.
   - `test_create_event_reserved_custom_slug_error`: Create event with reserved slug, verify HTTP 400 error.
   - `test_legacy_uuid_event_backward_compatibility`: Verify a legacy event with 36-char UUID loads player form, admin dashboard, submissions, and locked schedule normally.
3. **Full Test Suite & Linting**:
   - Run `pytest` (all tests passing).
   - Run `ruff check .` and `ruff format --check .`.
