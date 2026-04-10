# 👑 KingShot Kingdom Appointment Planner

Welcome, Leadership! 🏰 

The **Kingdom Appointment Planner** is our specialized strategic tool for dominating the **Kingdom vs Kingdom (KvK)** events. In the heat of battle, every minute of a "King's Buff" counts. This tool ensures that our strongest players are perfectly synchronized with the kingdom's buffs to generate the maximum possible points for our glory!

---

## 🎯 Our Objective

The goal is simple: **Maximum Efficiency.** 

By collecting player resource data and availability, this tool uses a "Protected Greedy Algorithm" to automatically assign the most impactful players to our limited 30-minute buff windows, while giving administrators full control to lock in "must-have" appointments manually.

---

## ✨ Key Capabilities

*   **Dynamic Player Fetching:** Players just enter their ID; the tool automatically grabs their name and avatar from the game!
*   **Smart Prioritization:** Automatically ranks players based on their potential point contribution (Speedups, TrueGold, etc.).
*   **Independent Daily Schedules:** Manages separate calendars for **Construction (Day 1)**, **Troop Training (Day 4)**, and **Research (Day 5)**.
*   **Secret Admin Dashboard:** A private, tabbed interface to manage everything without players seeing the behind-the-scenes magic.
*   **Manual Overrides:** Directly assign a player to a specific slot or "Lock" an automated assignment to protect it from changes.
*   **Real-time Analytics:** Search, filter, and sort alliance contributions and player submissions instantly.
*   **Finalized View:** A clean, read-only page to share with the entire kingdom once the schedule is set.

---

## 📸 Application Preview

> [!TIP]
> **[ PLACEHOLDER: Insert a screenshot of the Dark Mode Landing Page here ]**

---

## 📖 Administrator's Tutorial

Getting your kingdom organized is easy! Just follow these steps:

### 1. Create the Event

On the home page, give your event a name (e.g., "KvK Season 10 - March"). Hit **Create Event**, and you'll be given three very important links:

*   **Player URL:** Send this to everyone!
*   **Admin URL:** **SAVE THIS.** This is your private key to managing the schedule.
*   **Finalized Schedule URL:** Share this once you are ready for everyone to see their times.

> **[ PLACEHOLDER: Insert a screenshot of the Event Success Page here ]**

### 2. Collect Submissions

As players enter their IDs and availability, you'll see them pop up in your **Admin Dashboard**. You can use the "Refresh Player Data" button at any time to sync the latest nicknames and avatars from the game.

### 3. Assign Appointments

When you're ready to build the schedule:

1.  Go to the **Admin Dashboard**.
2.  Click **Assign Appointments**. The system will instantly fill the slots for all 3 days, prioritizing players with the most resources.
3.  **Manual Tweak:** Notice a specific slot needs a specific player? Use the dropdown in the submissions table to manually "Set" them into a slot.
4.  **Locking:** Click the **Lock** button on any slot to make it permanent. Locked slots won't be moved if you click "Assign Appointments" again.

> **[ PLACEHOLDER: Insert a screenshot of the Admin Dashboard with Tabs here ]**

### 4. Publish

Once the schedule looks perfect, just tell your players to check the **Finalized Schedule URL**. It's a clean, mobile-friendly view of exactly who goes where.

---

## 💾 Maintenance & Backups

We've included a handy utility script to keep your kingdom's data safe. You can run these from your host machine.

### 1. Take a Backup
To create a timestamped copy of your database:
```bash
./scripts/db_util.sh backup
```

**Advanced Options:**
*   **Custom Container Name:** `./scripts/db_util.sh -c my-container-name backup`
*   **Custom Backup Directory:** `./scripts/db_util.sh -d /path/to/backups backup`

### 2. Restore from Backup
To restore your data (Warning: this overwrites the current database):
```bash
./scripts/db_util.sh restore backups/planner_backup_TIMESTAMP.db
```
You can also use the `-c` flag during restore if your container name is different.

---

## 🚀 Technical Setup (For the Tech-Savvy)

The app is fully dockerized for easy deployment on any home server or VPS.

1.  **Install Docker and Docker Compose.**
2.  **Clone this repo.**
3.  **Launch:**
    ```bash
    docker-compose up --build -d
    ```
4.  **Access:** Open your browser to `http://localhost:12348`.

---

## 🛡️ Security Note

The **Admin URL** contains a unique "secret" key. Anyone with this link has full control over your event. Treat it like your kingdom's treasury key—don't share it publicly!

---

*Built with ❤️ for the KingShot community.* ⚔️
