#!/bin/bash

# Database Utility Script for KingShot KvK Planner
# Supports: backup, restore

# Default values
CONTAINER_NAME="kvk-appt-web-1"
DB_PATH="/app/data/planner.db"
BACKUP_DIR="./backups"

usage() {
    echo "Usage: $0 [options] [backup|restore] [filename]"
    echo ""
    echo "Options:"
    echo "  -c <name>    Docker container name (default: $CONTAINER_NAME)"
    echo "  -d <dir>     Backup directory (default: $BACKUP_DIR)"
    echo ""
    echo "Examples:"
    echo "  $0 backup                          # Use defaults"
    echo "  $0 -c my-custom-container backup   # Custom container name"
    echo "  $0 -d /tmp/backups backup          # Custom backup directory"
    echo "  $0 restore backups/file.db         # Restore a specific file"
    exit 1
}

# Parse options
while getopts "c:d:h" opt; do
    case $opt in
        c) CONTAINER_NAME="$OPTARG" ;;
        d) BACKUP_DIR="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND-1))

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
        echo "Creating live backup of $DB_PATH from container '$CONTAINER_NAME'..."
        
        # Use sqlite3 .backup for a consistent copy of a live database
        docker exec "$CONTAINER_NAME" sqlite3 "$DB_PATH" ".backup '/app/data/temp_backup.db'"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to create backup inside container."
            exit 1
        fi

        docker cp "$CONTAINER_NAME:/app/data/temp_backup.db" "$BACKUP_DIR/$FILENAME"
        docker exec "$CONTAINER_NAME" rm "/app/data/temp_backup.db"
        
        if [ $? -eq 0 ]; then
            echo "Backup successfully saved to: $BACKUP_DIR/$FILENAME"
        else
            echo "Error: Failed to copy backup from container."
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
        
        echo "Restoring database from $RESTORE_FILE to container '$CONTAINER_NAME'..."
        echo "WARNING: This will overwrite the current live database!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Restore cancelled."
            exit 1
        fi
        
        docker cp "$RESTORE_FILE" "$CONTAINER_NAME:$DB_PATH"
        if [ $? -eq 0 ]; then
            echo "Restore complete. You may need to restart the container if the schema changed."
        else
            echo "Error: Restore failed."
        fi
        ;;
        
    *)
        usage
        ;;
esac
