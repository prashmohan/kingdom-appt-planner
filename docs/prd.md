# **Product Requirements Document: KingShot Kingdom Appointment Planner**

## **1\. Executive Summary**

**Project Goal:** A high-precision coordination system for KingShot server leadership to manage 30-minute "King's Buff" windows during major events (Construction, Troop Training, Research).

**Core Value:** Maximize Kingdom-wide point generation by ensuring high-capacity players occupy limited buff windows. The system uses a resource-prioritized greedy algorithm that respects administrative "Confirmation" locks and maintains separate schedules for each event day.

**Key Features:** Modern dark theme, 49-slot daily schedule with interval labeling, multi-day submissions, independent per-day distribution logic, and tabbed administrative management.

## **2\. User Roles**

### **2.1 Player (Submitter)**

* **Submission:** Enters resource counts and selects feasible 30-minute windows for all active days (Day 1, Day 4, and Day 5) in a single form.
* **Visibility:** Views live schedules and their assignment status (Confirmed/Pending/Waitlisted).  
* **Constraints:** One submission record per Player ID for each day type. Submitting again overwrites all previous data for that player in that event.

### **2.2 Administrator (Kingdom Leadership)**

* **Event Management:** Initializes new KvK/Event instances. All 3 days (Construction, Training, Research) are active by default.
* **Validation & Locking:** Manually "Confirms" or "Unlocks" slots. Confirmed slots are immune to algorithmic redistribution.
* **Manual Assignment:** Directly assigns a player to a specific available slot via a dropdown menu.
* **Optimization:** Triggers the distribution engine to fill gaps independently for each day.
* **Visualization:** Tabbed views for each day type, featuring demand heatmaps and alliance impact summaries.

## **3\. Functional Requirements: Player Submission Page**

### **3.1 Compact Multi-Day Form**

The form displays resource inputs and availability grids for all active days simultaneously using a responsive multi-column layout to minimize scrolling.

* **Day 1: Construction:** Requires "Speedups" and "TrueGold".  
* **Day 4: Troop Training:** Requires "Speedups".  
* **Day 5: Research:** Requires "Speedups" and "TrueGold Dust".

### 3.2 Robust Submission Handling

* **Primary Key:** A composite of Event ID, Player ID, and Day/Type.
* **Overwrite Policy:** Every form submission performs a "delete-then-insert" operation for that specific player and event, ensuring the latest submission is the single source of truth.

### **3.3 Feasibility Selection**

* **Independent Grids:** Players use a separate 49-slot grid for each day to indicate their specific availability.
* **Interval Labeling:** Slots are clearly labeled with their 30-minute time interval (e.g., `23:45-00:15` for the pre-reset slot).

## **4\. Functional Requirements: Administrator Page**

### **4.1 Tabbed Interface**

The admin dashboard is organized into tabs (Construction, Training, Research) to declutter the view. Each tab contains:
*   The 49-slot schedule grid with heatmap coloring.
*   An alliance-level summary table for that specific day.
*   A filtered list of submissions for that specific day.

### **4.2 Advanced Management**

* **Manual Assignment Dropdown:** Admins can select from a list of currently unassigned slots to manually place a player.
* **Confirmation Toggle:** Every assigned slot can be toggled between "Lock" and "Unlock".
* **Rich Grid Data:** Schedule cells display the player's alliance and name (e.g., `[ALLIANCE] PlayerName`).

## **5\. Distribution Algorithm Logic**

### 5.1 Per-Day Independence

The greedy algorithm runs as a loop through all active days. For each day, it performs an isolated distribution process, ensuring that availability selections for one day do not impact the schedule of another.

### **5.2 Protected Greedy Distribution**

1. **Ranking:** Sort all players for the current day by Resource Score (DESC), then Timestamp (ASC).
2. **Iterative Allocation:** For each player, assign the first available slot from their "Feasible" list that isn't already occupied (either by a Lock or a higher-ranked player).

## **6\. UX/UI Requirements**

### **6.1 Modern Dark Theme**

* **Palette:** Charcoal background, off-white text, and Amber/Gold accents.
* **Typography:** Clean, minimalistic sans-serif.
* **Visual Hierarchy:** Important actions (Event Creation, Distribution) use high-contrast gold buttons.

### **6.2 Informative Onboarding**

* **Helper Text:** The landing page includes an introduction explaining the tool's strategic role in the KingShot KvK event to encourage player participation.
