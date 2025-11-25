#!/usr/bin/env python3
"""Reset Azurite storage to a clean state for local Postman testing.

This script:
1. Deletes all tables (ClaimedNames, AuditLogs, SlugMappings)
2. Recreates them empty
3. Seeds SlugMappings with current Azure resource types from GitHub

Usage:
    python tools/reset_azurite.py

Prerequisites:
    - Azurite must be running (typically on 127.0.0.1:10002)
    - Connection string must be set to UseDevelopmentStorage=true
"""

import logging
import sys
from datetime import datetime

from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError

# Table names from app/constants.py
NAMES_TABLE_NAME = "ClaimedNames"
AUDIT_TABLE_NAME = "AuditLogs"
SLUG_TABLE_NAME = "SlugMappings"

# Azurite connection for local development
AZURITE_CONNECTION = "UseDevelopmentStorage=true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def reset_azurite():
    """Reset Azurite storage to clean state."""
    
    logger.info("=" * 70)
    logger.info("RESETTING AZURITE STORAGE FOR LOCAL POSTMAN TESTING")
    logger.info("=" * 70)
    
    try:
        # Connect to Azurite
        logger.info("Connecting to Azurite...")
        table_service = TableServiceClient.from_connection_string(AZURITE_CONNECTION)
        logger.info("✓ Connected to Azurite successfully")
        
        # Delete and recreate each table
        tables_to_reset = [
            (NAMES_TABLE_NAME, "Claimed names table"),
            (AUDIT_TABLE_NAME, "Audit logs table"),
            (SLUG_TABLE_NAME, "Slug mappings table"),
        ]
        
        for table_name, description in tables_to_reset:
            try:
                logger.info(f"Deleting table: {table_name} ({description})...")
                table_service.delete_table(table_name)
                logger.info(f"✓ Deleted {table_name}")
            except ResourceNotFoundError:
                logger.info(f"  (Table {table_name} did not exist)")
            
            # Recreate the table
            logger.info(f"Creating table: {table_name}...")
            table_service.create_table(table_name)
            logger.info(f"✓ Created {table_name}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("AZURITE RESET COMPLETE")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Storage is now ready for Postman testing:")
        logger.info(f"  - {NAMES_TABLE_NAME}: Empty (ready for claims)")
        logger.info(f"  - {AUDIT_TABLE_NAME}: Empty (ready for audit logs)")
        logger.info(f"  - {SLUG_TABLE_NAME}: Empty (slugs loaded on sync)")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run Postman test 1.5 'Slug Sync - Fetch and Update' to populate SlugMappings")
        logger.info("  2. Then run remaining tests (claim, release, audit, etc.)")
        logger.info("")
        
        return 0
        
    except Exception as e:
        logger.error(f"✗ Error resetting Azurite: {e}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("  - Is Azurite running? (should be on 127.0.0.1:10002)")
        logger.error("  - Check AZURITE_CONNECTION string in this script")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(reset_azurite())
