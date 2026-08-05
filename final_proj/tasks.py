import logging
from celery import shared_task
from .backup import run_scheduled_backup

logger = logging.getLogger(__name__)

@shared_task
def run_database_backup():
    """Scheduled task for enterprise database backup."""
    logger.info("Starting scheduled database backup...")
    try:
        run_scheduled_backup()
        logger.info("Scheduled database backup completed.")
        return True
    except Exception as e:
        logger.error(f"Scheduled database backup failed: {str(e)}")
        return False
