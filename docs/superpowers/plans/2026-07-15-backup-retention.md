# Configurable Backup Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify the backup script to automatically delete backups older than 30 days (default) while allowing customization through a command-line flag.

**Architecture:** Initialize a default `RETENTION_DAYS=30` variable, parse option `-r` in `getopts`, and execute `find` to delete files matching `planner_backup_*.db` older than `RETENTION_DAYS` days.

**Tech Stack:** Bash, GNU find.

## Global Constraints
- Naming & copy rules: Match file pattern `planner_backup_*.db`.
- OS: Linux.
- Backward compatibility: Existing cron command `db_util.sh backup` must function as before but clean up backups older than 30 days.

---

### Task 1: Add Configurable Retention to `db_util.sh`

**Files:**
- Modify: `scripts/db_util.sh`

**Interfaces:**
- Consumes: Existing backup creation command.
- Produces: Updated `-r <days>` option, and automated cleanup logic inside the `backup` subcommand.

- [ ] **Step 1: Declare default retention variable**
  
  Add `RETENTION_DAYS=30` near the top of the file under default values.
  
  In [scripts/db_util.sh](file:///home/prmohan/projects/kvk-appt/scripts/db_util.sh):
  ```bash
  # Default values
  CONTAINER_NAME="kvk-appt-web-1"
  DB_PATH="/app/data/planner.db"
  BACKUP_DIR="./backups"
  RETENTION_DAYS=30
  ```

- [ ] **Step 2: Document `-r` in `usage()`**
  
  Update `usage()` to document the new `-r <days>` option.
  
  In [scripts/db_util.sh](file:///home/prmohan/projects/kvk-appt/scripts/db_util.sh):
  ```bash
  echo "Options:"
  echo "  -c <name>    Docker container name (default: $CONTAINER_NAME)"
  echo "  -d <dir>     Backup directory (default: $BACKUP_DIR)"
  echo "  -r <days>    Number of days of backups to retain (default: $RETENTION_DAYS)"
  ```

- [ ] **Step 3: Support `-r` in `getopts`**
  
  Add `r:` to the `getopts` pattern, and set `RETENTION_DAYS` when matched.
  
  In [scripts/db_util.sh](file:///home/prmohan/projects/kvk-appt/scripts/db_util.sh):
  ```bash
  # Parse options
  while getopts "c:d:r:h" opt; do
      case $opt in
          c) CONTAINER_NAME="$OPTARG" ;;
          d) BACKUP_DIR="$OPTARG" ;;
          r) RETENTION_DAYS="$OPTARG" ;;
          h) usage ;;
          *) usage ;;
      esac
  done
  ```

- [ ] **Step 4: Implement find-based retention cleanup in the backup subcommand**
  
  Modify the `backup)` case block in `scripts/db_util.sh` to run the `find` deletion logic after a successful copy.
  
  In [scripts/db_util.sh](file:///home/prmohan/projects/kvk-appt/scripts/db_util.sh):
  ```bash
        if [ $? -eq 0 ]; then
            echo "Backup successfully saved to: $BACKUP_DIR/$FILENAME"
            
            # Retention cleanup
            echo "Cleaning up backups in $BACKUP_DIR older than $RETENTION_DAYS days..."
            find "$BACKUP_DIR" -name "planner_backup_*.db" -type f -mtime +"$RETENTION_DAYS" -delete
            echo "Cleanup complete."
        else
            echo "Error: Failed to copy backup from container."
        fi
  ```

- [ ] **Step 5: Verify syntax and style using ruff/lint checks**
  
  Check if the workspace requires formatting. Since it is a bash script, verify that there are no syntax errors by running bash check:
  
  Run: `bash -n scripts/db_util.sh`
  Expected: No output (exit code 0, indicating syntax is correct).

- [ ] **Step 6: Commit the script changes**
  
  Run:
  ```bash
  git add scripts/db_util.sh
  git commit -m "feat: add backup retention and cleanup to db_util.sh"
  ```

---

### Task 2: Test & Verify Retention Behavior

**Files:**
- Create/Modify: None (Verification task)

- [ ] **Step 1: Setup test directory and mock backups**
  
  Create a temporary backup test directory and generate mock backups with varied modification times.
  
  Run:
  ```bash
  mkdir -p ./test_backups
  touch -d "35 days ago" ./test_backups/planner_backup_old.db
  touch -d "10 days ago" ./test_backups/planner_backup_recent.db
  touch ./test_backups/planner_backup_fresh.db
  ls -lh ./test_backups
  ```
  Expected: Three mock backup files created with correct timestamps.

- [ ] **Step 2: Test default retention behavior (30 days)**
  
  Run the backup utility directing backups to the test directory using default retention (which should be 30 days).
  
  Run:
  ```bash
  ./scripts/db_util.sh -c kingdom-appt-planner-web-1 -d ./test_backups backup
  ```
  Expected:
  - Creates a new backup file.
  - Cleans up `planner_backup_old.db` (35 days ago).
  - Retains `planner_backup_recent.db` (10 days ago), `planner_backup_fresh.db` (0 days ago), and the newly created backup.
  
  Verify files remaining in `./test_backups`:
  Run: `ls -lh ./test_backups`
  Expected:
  - `planner_backup_recent.db` exists.
  - `planner_backup_fresh.db` exists.
  - `planner_backup_old.db` does NOT exist.
  - The newly created backup file exists.

- [ ] **Step 3: Test custom retention threshold (e.g., 5 days)**
  
  Touch another old-ish file in `./test_backups` (10 days old):
  Run: `touch -d "10 days ago" ./test_backups/planner_backup_recent.db`
  
  Run the backup script specifying a retention period of 5 days:
  Run: `./scripts/db_util.sh -c kingdom-appt-planner-web-1 -d ./test_backups -r 5 backup`
  
  Verify files remaining in `./test_backups`:
  Run: `ls -lh ./test_backups`
  Expected:
  - `planner_backup_recent.db` is deleted (10 days > 5 days).
  - `planner_backup_fresh.db` and the new backup files remain.

- [ ] **Step 4: Cleanup test environment**
  
  Remove the temporary test directory.
  
  Run: `rm -rf ./test_backups`
  Expected: test directory deleted.
