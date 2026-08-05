import logging
from celery import shared_task
from django.core.cache import cache
from final_proj.celery import DLQTask
from accounts.services import get_governance_analytics

logger = logging.getLogger(__name__)

@shared_task(bind=True, base=DLQTask, max_retries=3)
def refresh_analytics_cache(self):
    """
    Precomputes governance analytics and stores them in cache.
    Reduces DB load for dashboards.
    """
    try:
        analytics = get_governance_analytics()
        
        # Store in default cache for 6 hours (21600 seconds)
        cache.set('governance_analytics_cache', analytics, timeout=21600)
        
        logger.info("Successfully refreshed governance analytics cache.")
        return True
    except Exception as exc:
        logger.error(f"Error in refresh_analytics_cache: {str(exc)}")
        raise self.retry(exc=exc, countdown=120)
