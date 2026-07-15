# Design Spec: Configurable Backup Retention in `db_util.sh`

This design document outlines the implementation of a configurable retention policy for database backups created by `db_util.sh`.

## 1. Goal
Only retain the last 30 days (or a user-specified number of days) of database backups in the backup directory, automatically cleaning up older backups during the backup command.

## 2. Requirements & Constraints
* **Retroactive Compatibility**: Must work seamlessly with existing crontabs. The default retention must be 30 days.
* **Flexibility**: Allow the user to override the retention period using a command-line flag `-r <days>`.
* **Safety**: Only delete files matching the specific backup pattern `planner_backup_*.db` within the configured backup directory.
* **OS**: Running on Linux (using bash and GNU find).

## 3. Detailed Changes in `db_util.sh`

### A. Default Variable Initialization
Initialize `RETENTION_DAYS` near the top of [db_util.sh](file:///home/prmohan/projects/kvk-appt/scripts/db_util.sh):
```bash
RETENTION_DAYS=30
```

### B. Usage Documentation
Update the `usage()` function to document the new option:
```bash
echo "  -r <days>    Number of days of backups to retain (default: \$RETENTION_DAYS)"
```

### C. Options Parsing
Update the `getopts` loop to accept `-r`:
```bash
while getopts "c:d:r:h" opt; do
    case \$opt in
        c) CONTAINER_NAME="\$OPTARG" ;;
        d) BACKUP_DIR="\$OPTARG" ;;
        r) RETENTION_DAYS="\$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done
```

### D. Backup Subcommand Cleanup Flow
In the `backup)` case block, after successfully copying the backup from the container:
```bash
if [ \$? -eq 0 ]; then
    echo "Backup successfully saved to: \$BACKUP_DIR/\$FILENAME"
    
    # Retention cleanup
    echo "Cleaning up backups in \$BACKUP_DIR older than \$RETENTION_DAYS days..."
    find "\$BACKUP_DIR" -name "planner_backup_*.db" -type f -mtime +"\$RETENTION_DAYS" -delete
    echo "Cleanup complete."
else
    echo "Error: Failed to copy backup from container."
fi
```

## 4. Testing & Verification Plan
Since this runs a shell command calling `find` and `docker`, we can test the script manually:
1. Run a test run with a very small retention period (e.g. `-r 0` to prune files, or create mock files with old timestamps using `touch -d`).
2. Verify that files older than the retention threshold are deleted, and newer ones are kept.
3. Validate that standard runs without `-r` default to 30 days.
