# Design Specification: Submissions Export and Import

This document specifies the design for adding export and import functionalities for player submissions within the Kingdom vs Kingdom (KvK) Appointment Planner.

## 1. Objectives

- Allow administrators to export all player submissions for an event into a single JSON file.
- Allow administrators to import previously exported JSON submission files into the current event.
- Maintain data consistency by cleaning up stale assignments/submissions when updating matching player profiles.
- Provide a clean, native, and premium UI integration directly in the Global Actions card of the Admin Dashboard.

## 2. JSON Schema for Submissions Export/Import

The exported JSON will be a JSON array of objects, where each object represents a single submission record.

```json
[
  {
    "day_type": "construction",
    "player_name": "John Doe",
    "player_id": "12345",
    "avatar_url": "/static/uploads/avatar_123.png",
    "backpack_url": "/static/uploads/backpack_456.jpg",
    "alliance_name": "ALLIANCE_A",
    "resources": 15000.0,
    "raw_data": "{\"speedups\": 500, \"truegold\": 0, \"tempered_truegold\": 0}",
    "feasible_slots": "[0, 1, 2]",
    "status": "Pending"
  }
]
```

### Data Fields Specification:
- `day_type` (TEXT, NOT NULL): The day category (`construction`, `training`, or `research`).
- `player_name` (TEXT, NOT NULL): Name of the player.
- `player_id` (TEXT, NOT NULL): ID of the player.
- `avatar_url` (TEXT): URL to the player's avatar.
- `backpack_url` (TEXT): URL to the player's backpack screenshot.
- `alliance_name` (TEXT): Alliance designation.
- `resources` (REAL, NOT NULL): The calculated score/points based on their speedups/materials.
- `raw_data` (TEXT, NOT NULL): JSON serialized string containing raw item counts.
- `feasible_slots` (TEXT, NOT NULL): JSON serialized string containing array of slot indices.
- `status` (TEXT): State of the submission (e.g. `Pending` or `Approved`).

## 3. Backend Routes & Architecture

We will implement two new routes in `app/__init__.py`:

### 3.1. Export Route: `export_submissions`

- **URL**: `/admin/<event_uid>/export_submissions`
- **Method**: `GET`
- **Security Check**: Verify that `secret` query parameter matches the event's `admin_secret`.
- **Logic**:
  1. Retrieve all columns (except local database IDs and event_uids to prevent conflicts) from the `submissions` table matching the event's `uid`.
  2. Serialize query results into a list of dictionaries matching the JSON schema.
  3. Respond with a file download containing the JSON content:
     - Header: `Content-Type: application/json`
     - Header: `Content-Disposition: attachment; filename=submissions_<event_uid>_<timestamp>.json`

### 3.2. Import Route: `import_submissions`

- **URL**: `/admin/<event_uid>/import_submissions`
- **Method**: `POST`
- **Security Check**: Verify that `secret` form parameter matches the event's `admin_secret`.
- **Logic**:
  1. Read and parse the uploaded file (`submissions_file`).
  2. Validate that it contains a valid JSON array of objects.
  3. Validate that each object contains the required fields: `day_type`, `player_name`, `player_id`, `resources`, `raw_data`, `feasible_slots`. If not, abort and return a user-friendly error flash message.
  4. Perform import in a single transaction:
     - Extract all unique `player_id`s from the imported list.
     - For each unique `player_id` found in the import payload, delete all existing submissions and assignments in the database for the current `event_uid` to avoid conflicts:
       ```sql
       DELETE FROM submissions WHERE event_uid = ? AND player_id = ?
       DELETE FROM assignments WHERE event_uid = ? AND player_id = ?
       ```
     - Insert each imported submission with:
       - `id` generated as `f"{event_uid}_{player_id}_{day_type}"`
       - `event_uid` mapped to the current event's `uid`
       - Other fields populated from the JSON object.
  5. Log the operation details to the audit log.
  6. Flash a success message: `"Successfully imported N submissions for M players."`
  7. Redirect back to the Admin Dashboard.

## 4. Frontend & User Interface Changes

### 4.1. Admin Dashboard Controls (`admin_dashboard.html`)
The new actions will be added to the Global Actions card.
- **Export button**: Anchored inline next to the "Refresh Player Data" button.
- **Import button**: Styled file label wrapping a hidden file input. Selecting a JSON file immediately triggers the form's `submit` action.

### 4.2. Flash Alerts Notification Block
Add a display container below the main title header in `admin_dashboard.html` to show error/success messages.

## 5. Verification Plan

### 5.1. Automated Tests
Create new unit and route tests in `tests/test_routes.py` covering:
- Exporting submissions: Verify security (wrong secret rejects), status code (200), file download headers, and JSON structure of response.
- Importing submissions:
  - Verify invalid/malformed JSON returns error flash.
  - Verify missing fields in JSON objects returns error flash.
  - Verify successful import creates matching submissions in the database.
  - Verify upserting deletes existing submissions and assignments for imported players.
  - Verify event_uid mapping works correctly.

### 5.2. Manual Verification
1. Open the Admin Dashboard.
2. Enter player submissions.
3. Click "Export Submissions" and verify the file downloads correctly.
4. Verify the contents of the downloaded file.
5. Upload the exported file using "Import Submissions" and verify the success notification and that the submissions persist.
