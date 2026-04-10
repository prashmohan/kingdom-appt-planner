#!/bin/bash

# Database Utility Script for KingShot KvK Planner
# Supports: backup, restore

CONTAINER_NAME="kvk-appt-web-1"
DB_PATH="/app/data/planner.db"
BACKUP_DIR="./backups"

usage() {
    echo "Usage: $0 [backup|restore] [filename]"
    echo ""
    echo "Examples:"
    echo "  $0 backup              # Creates a timestamped backup in $BACKUP_DIR"
    echo "  $0 restore backup.db   # Restores the specified backup file"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

COMMAND=$1

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

case $COMMAND in
    backup)
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        FILENAME="planner_backup_${TIMESTAMP}.db"
        echo "Creating live backup of $DB_PATH..."
        
        # Use sqlite3 .backup for a consistent copy of a live database
        docker exec "$CONTAINER_NAME" sqlite3 "$DB_PATH" ".backup '/app/data/temp_backup.db'"
        docker cp "$CONTAINER_NAME:/app/data/temp_backup.db" "$BACKUP_DIR/$FILENAME"
        docker exec "$CONTAINER_NAME" rm "/app/data/temp_backup.db"
        
        if [ $? -eq 0 ]; then
            echo "Backup saved to: $BACKUP_DIR/$FILENAME"
        else
            echo "Error: Backup failed."
        fi
        ;;
        
    restore)
        if [ -z "$2" ]; then
            echo "Error: Please specify the file to restore."
            usage
        fi
        
        RESTORE_FILE=$2
        if [ ! -f "$RESTORE_FILE" ]; then
            echo "Error: File $RESTORE_FILE not found."
            exit 1
        fi
        
        echo "Restoring database from $RESTORE_FILE..."
        echo "WARNING: This will overwrite the current live database!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Restore cancelled."
            exit 1
        fi
        
        docker cp "$RESTORE_FILE" "$CONTAINER_NAME:$DB_PATH"
        echo "Restore complete. You may need to restart the container if the schema changed."
        ;;
        
    *)
        usage
        ;;
esac
