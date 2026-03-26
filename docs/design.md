# **Design Document: KingShot Kingdom Appointment Planner**

## **1\. System Architecture**

The system follows a monolithic Model-View-Controller (MVC) pattern to minimize complexity and external dependencies.

* **Language:** Python 3.10+  
* **Web Framework:** **Flask** (Lightweight, low overhead).  
* **Database:** **SQLite** (Zero-configuration, serverless, single-file storage).  
* **Frontend:** HTML5, Tailwind CSS (via CDN), and Vanilla JavaScript.
* **Theme:** Modern minimalistic dark theme (Charcoal background, Gold/Amber accents).
* **Deployment:** **Docker Container** via Docker Compose.

## **2\. Data Model (SQLite Schema)**

### 2.1 Table: events

Stores metadata for independent KvK/Event instances.

* id: INTEGER PRIMARY KEY (Auto-increment)  
* uid: TEXT UNIQUE (Randomly generated unique string for URLs)  
* name: TEXT  
* active_days: TEXT (JSON object indicating active types, e.g., {"construction": true, "training": true, "research": true})
* admin\_secret: TEXT (Unique secret key generated upon creation)  
* created\_at: TIMESTAMP DEFAULT CURRENT\_TIMESTAMP

### 2.2 Table: submissions

Stores player intent and resource data for a specific day/type within an event.

* id: TEXT PRIMARY KEY (Format: event\_uid\_player\_id\_day\_type)  
* event\_uid: TEXT (FK to events.uid)
* day\_type: TEXT (e.g., "construction", "training", "research")
* player\_name: TEXT  
* player\_id: TEXT (Value is trimmed and treated as case-insensitive to prevent duplicates)
* alliance\_name: TEXT  
* resources: REAL (Calculated weighted score)  
* raw\_data: TEXT (JSON string)  
* feasible\_slots: TEXT (JSON array of indices 0-48)  
* timestamp: TIMESTAMP  
* status: TEXT (Pending, Confirmed, Waitlisted)

### 2.3 Table: assignments

The finalized schedule for an event, maintained independently for each day type.

* event\_uid: TEXT (FK to events.uid)  
* day\_type: TEXT (FK to submissions.day_type)
* slot\_index: INTEGER (0-48)  
* player\_id: TEXT  
* is\_locked: BOOLEAN (Admin confirmation flag)
* PRIMARY KEY (event_uid, day_type, slot_index)

### 2.4 Resource Score Calculation

To enable ranking across different resource types, raw inputs are converted into a single `resources` score. All calculations are normalized to an equivalent of "speedup minutes".

*   **Base Unit:** 1 Speedup (Minute) = 1 point.
*   **Weights:**
    *   `Construction`: 1 TrueGold = 100 points.
    *   `Research`: 1 TrueGold Dust = 150 points.
*   **Formulae:**
    *   `Construction Score` = `speedups` + (`truegold` * 100)
    *   `Training Score` = `speedups`
    *   `Research Score` = `speedups` + (`truegold_dust` * 150)

## **3\. Core Logic: Protected Greedy Algorithm**

The distribution algorithm runs independently for each active `day_type` in the event.

1. **Preparation:** 
    * Fetch active days for the event.
    * For each day:
        * Fetch locked assignments (Unavailable).
        * Clear all non-locked assignments.
        * Fetch all submissions for that specific `day_type`.
2. **Ranking:** Sort players by resources DESC, then timestamp ASC.  
3. **Allocation:** Loop through ranked players; assign them to the first free slot in their day-specific `feasible_slots` list.  
4. **Persistence:** Update the assignments table with Pending results.

## **4\. API & Routing**

### **4.1 General & Player Routes**

* GET /: **Landing Page**. Introduction to the system and event creation form.
* POST /create: Instantiates a new event. All 3 days are active by default. Redirects to Success page.
* GET /success/\<event\_uid\>: Displays the unique Player and Admin URLs.
* GET /event/\<event\_uid\>: **Player Submission Form**. Shows resource inputs and availability grids for all 3 days.
* POST /event/\<event\_uid\>/submit: Processes player data using a "delete-then-insert" pattern for robustness.
* GET /event/\<event\_uid\>/schedule: Public read-only view of the schedules for all active days.

### **4.2 Administrator Routes (Secret Protected)**

* GET /admin/\<event\_uid\>?secret=\<admin\_secret\>: **Admin Dashboard**. Tabbed interface for each day.
* POST /admin/\<event\_uid\>/distribute: Triggers the Greedy Algorithm for all days.  
* POST /admin/\<event\_uid\>/confirm: Sets is\_locked \= 1 for a specific slot/day.
* POST /admin/\<event\_uid\>/unlock: Sets is\_locked \= 0 for a specific slot/day.
* POST /admin/\<event\_uid\>/manual_assign: Manually assigns and locks a specific slot for a submission.
* POST /admin/\<event\_uid\>/delete: Deletes a submission and clears the assigned slot.

## **5\. UI/UX Implementation Details**

### **5.1 The 49-Slot Selection Grid**

* **Structure:** A grid of 49 div elements representing 30-minute blocks.  
* **Interval Labeling:** Slots are labeled as intervals (e.g., Slot 0 is `23:45-00:15`).
* **"Paint-to-Select" Logic:** Uses JS to toggle slot states on drag/click.
* **Per-Day Independence:** Each day has its own independent grid and hidden input.

### **5.2 Administrative Visualizations**

* **Tabbed Interface:** Separate views for Construction, Training, and Research.
* **Heatmap Saturation:** Opacity based on player density per slot, per day.
* **Alliance Impact Summary:** Aggregated stats (Score, Submissions, Assignments) per alliance, per day.
* **Rich Assignments:** Grid cells display `[Alliance] PlayerName`.

## **6\. Docker Implementation Details**

### **6.1 Container Strategy**

Uses `python:3.12-slim`. Port `12348` on the host maps to `5000` in the container.

### **6.2 Docker Compose**

Uses version `2.4` for compatibility. Employs a named volume `planner_data` for the SQLite database.

## **7\. Test Cases**

Updated to reflect per-day schedule independence and the new dark theme UI.

## **8\. Deployment Plan**

1. **Database Initialization:** Idempotent check for table existence on startup.
2. **Persistence:** Managed via Docker named volumes.
