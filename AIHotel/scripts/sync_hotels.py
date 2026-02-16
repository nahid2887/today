#!/usr/bin/env python3
"""
Hotel Data Sync Script for Cron/Systemd
========================================

This script syncs hotel data from the backend API to ChromaDB.
Designed to run daily via systemd timer or cron.

Usage:
    python scripts/sync_hotels.py

Logs:
    /var/log/hotel-sync.log (if writable)
    ./logs/hotel-sync.log (fallback)
"""
import asyncio
import sys
import logging
from datetime import datetime
from pathlib import Path
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project directory
os.chdir(project_root)

from main import sync_hotel_data, initialize_system, get_hotel_count

# Configure logging
log_dir = Path("/var/log")
if not log_dir.is_dir() or not os.access(log_dir, os.W_OK):
    # Fallback to local logs directory
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

log_file = log_dir / "hotel-sync.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    """Run the sync process with comprehensive error handling and logging."""
    start_time = datetime.now()
    
    logger.info("=" * 70)
    logger.info("HOTEL DATA SYNC STARTED")
    logger.info(f"Timestamp: {start_time.isoformat()}")
    logger.info(f"Working Directory: {os.getcwd()}")
    logger.info(f"Log File: {log_file}")
    logger.info("=" * 70)
    
    try:
        # Initialize system
        logger.info("Initializing system components...")
        await initialize_system()
        logger.info("✓ System initialized successfully")
        
        # Check current database status
        logger.info("Checking current database status...")
        current_count = await get_hotel_count()
        logger.info(f"Current hotels in database: {current_count}")
        
        # Run sync
        logger.info("Starting hotel data synchronization...")
        result = await sync_hotel_data()
        
        # Calculate duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log results
        logger.info("-" * 70)
        logger.info("SYNC RESULTS:")
        logger.info(f"  Status: {result['status']}")
        logger.info(f"  Message: {result.get('message', 'N/A')}")
        logger.info(f"  Hotels Synced: {result['count']}")
        logger.info(f"  Duration: {duration:.2f} seconds")
        logger.info("-" * 70)
        
        if result['status'] == 'success':
            logger.info(f"✓ Successfully synced {result['count']} hotels to ChromaDB")
            
            # Verify the sync
            new_count = await get_hotel_count()
            logger.info(f"✓ Verification: {new_count} hotels now in database")
            
            if new_count != result['count']:
                logger.warning(f"⚠ Count mismatch: synced {result['count']} but database has {new_count}")
            
            return 0
        else:
            logger.error(f"✗ Sync failed: {result.get('message', 'Unknown error')}")
            return 1
            
    except Exception as e:
        logger.error(f"✗ Fatal error during sync: {e}", exc_info=True)
        return 1
    
    finally:
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.info("HOTEL DATA SYNC COMPLETED")
        logger.info(f"End Time: {end_time.isoformat()}")
        logger.info(f"Total Duration: {total_duration:.2f} seconds")
        logger.info("=" * 70)
        logger.info("")  # Empty line for readability


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n✗ Sync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}", exc_info=True)
        sys.exit(1)
