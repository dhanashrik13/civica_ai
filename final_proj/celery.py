import os
from celery import Celery, Task

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')

app = Celery('final_proj')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

class DLQTask(Task):
    """
    Base Celery Task with Hardened Circuit Breaker and DLQ routing.
    """
    _local_fail_cache = {} # Local fallback if Redis is down

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        from django.core.cache import cache
        
        # 1. HARDENED CIRCUIT BREAKER LOGIC
        fail_key = f"circuit_fail_{self.name}"
        try:
            fail_count = cache.get(fail_key, 0)
            cache.set(fail_key, fail_count + 1, 600)
        except Exception:
            # Fallback to local memory if Redis is down
            fail_count = self._local_fail_cache.get(self.name, 0)
            self._local_fail_cache[self.name] = fail_count + 1
            import logging
            logging.getLogger(__name__).error(f"[ASYNC HARDENING] Cache unreachable. Using local memory for circuit breaker.")

        if fail_count > 50:
            import logging
            logger = logging.getLogger(__name__)
            logger.critical(f"[CIRCUIT BREAKER] Tripped for {self.name}. Aborting retries to prevent queue storm.")
            self._route_to_dlq(exc, task_id, args, kwargs)
            return

        # 2. DLQ ROUTING
        if self.request.retries >= self.max_retries:
            self._route_to_dlq(exc, task_id, args, kwargs)
            
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def _route_to_dlq(self, exc, task_id, args, kwargs):
        """Internal helper to move task to Dead Letter Queue."""
        self.app.send_task(
            'final_proj.celery.process_dlq',
            args=(self.name, task_id, str(exc), args, kwargs),
            queue='dlq'
        )

@app.task(queue='dlq')
def process_dlq(failed_task_name, task_id, exc_str, args, kwargs):
    """Log or store the failed task details."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(
        f"DLQ Alert: Task {failed_task_name} (ID: {task_id}) failed "
        f"after max retries. Error: {exc_str}. Args: {args}, Kwargs: {kwargs}"
    )

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
