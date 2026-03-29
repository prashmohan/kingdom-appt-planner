#!/bin/bash

# Kingdom Appointment Planner - Database Utility
# Usage: ./scripts/db_util.sh {backup|restore} [backup_file]

CONTAINER_NAME=$(docker-compose ps -q web | head -n 1)
DB_PATH="/app/data/planner.db"
BACKUP_DIR="./backups"

# Check if container is running
if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Error: Web container not found. Is the application running?"
    echo "   Try: docker-compose up -d"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

case "$1" in
    backup)
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        FILENAME="$BACKUP_DIR/planner_backup_$TIMESTAMP.db"
        echo "⏳ Starting safe backup of $DB_PATH..."
        
        # Use Python inside the container to perform a safe online backup to a temporary file
        docker exec "$CONTAINER_NAME" python3 -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); dest = sqlite3.connect('/tmp/temp_backup.db'); conn.backup(dest); conn.close(); dest.close()"
        
        # Copy the temporary backup file from the container to the host
        docker cp "$CONTAINER_NAME":/tmp/temp_backup.db "$FILENAME"
        
        # Cleanup temp file in container
        docker exec "$CONTAINER_NAME" rm /tmp/temp_backup.db
        
        echo "✅ Backup successfully stored at: $FILENAME"
        ;;
        
    restore)
        if [ -z "$2" ]; then
            echo "❌ Error: Please specify the backup file to restore."
            echo "   Usage: $0 restore backups/planner_backup_YYYYMMDD_HHMMSS.db"
            exit 1
        fi
        if [ ! -f "$2" ]; then
            echo "❌ Error: Backup file '$2' not found."
            exit 1
        fi
        
        echo "⚠️  WARNING: This will overwrite the current live database!"
        read -p "Are you sure you want to continue? (y/N): " confirm
        if [[ $confirm != [yY] ]]; then
            echo "Aborted."
            exit 0
        fi

        echo "⏳ Restoring database from $2..."
        # Copy backup file into the container's temporary space
        docker cp "$2" "$CONTAINER_NAME":/tmp/restore.db
        
        # Use Python to safely restore
        docker exec "$CONTAINER_NAME" python3 -c "import sqlite3; dest = sqlite3.connect('$DB_PATH'); src = sqlite3.connect('/tmp/restore.db'); src.backup(dest); src.close(); dest.close()"
        
        # Cleanup
        docker exec "$CONTAINER_NAME" rm /tmp/restore.db
        
        echo "♻️  Restarting container to apply changes..."
        docker-compose restart web
        
        echo "✅ Database successfully restored and application restarted."
        ;;
        
    *)
        echo "Usage: $0 {backup|restore} [backup_file]"
        exit 1
        ;;
esac
