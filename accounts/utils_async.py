import logging
from django.db import transaction, models
from .models import PendingTask
from final_proj.celery import app
from django.utils import timezone

logger = logging.getLogger(__name__)

def dispatch_task_transactional(task_name, args=None, kwargs=None, queue='default'):
    """
    Ensures task persistence is atomic with the database transaction.
    Implements Task Debouncing and Priority Routing.
    """
    if args is None: args = []
    if kwargs is None: kwargs = dict()

    from django.conf import settings
    if hasattr(settings, 'CELERY_TASK_ROUTES') and task_name in settings.CELERY_TASK_ROUTES:
        queue = settings.CELERY_TASK_ROUTES[task_name].get('queue', queue)

    try:
        # DEBOUNCING LOGIC: Coalesce identical events
        debounce_tasks = [
            'accounts.tasks.recalculate_officer_metrics',
            'accounts.tasks.sync_citizen_profile_counters',
            'issues.tasks.update_dashboard_projections'
        ]
        
        if task_name in debounce_tasks:
            existing = PendingTask.objects.filter(
                task_name=task_name,
                args=args,
                kwargs=kwargs,
                status=PendingTask.Status.PENDING
            ).exists()
            
            if existing:
                logger.debug(f"[OUTBOX DEBOUNCE] Coalesced redundant task {task_name} with args {args}")
                return True

        pending = PendingTask.objects.create(
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            queue=queue,
            status=PendingTask.Status.PENDING
        )
    except Exception as e:
        logger.error(f"[OUTBOX] DB persistence failed for {task_name}: {str(e)}")
        return False

    def _execute_dispatch():
        try:
            # OPTIMIZATION: Use a strict 1-second timeout for the connection attempt
            # to ensure broker downtime never blocks the user request for long.
            # The Outbox Pattern (PendingTask) ensures data is never lost.
            with app.connection_for_write() as conn:
                conn.connect_timeout = 1.0 # Strict timeout
                app.send_task(
                    task_name, 
                    args=args, 
                    kwargs=kwargs, 
                    queue=queue,
                    connection=conn,
                    retry=False, # Do not retry in request thread
                    ignore_result=True # Do not wait for/connect to result backend
                )
            
            PendingTask.objects.filter(pk=pending.pk).update(
                status=PendingTask.Status.DISPATCHED,
                dispatched_at=timezone.now()
            )
        except Exception as e:
            # Expected failure if Redis is down. Outbox recovery worker will pick it up.
            logger.warning(f"[OUTBOX] Optimistic dispatch failed for {task_name} (Broker unreachable). Recovery will handle it. Error: {str(e)}")

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_execute_dispatch)
    else:
        _execute_dispatch()
    
    return True

def recover_pending_tasks(batch_size=1000):
    """
    Drains the Outbox by retrying tasks stuck in PENDING status.
    Implements adaptive batching, exponential backoff, and dead-letter queues.
    """
    now = timezone.now()
    
    with transaction.atomic():
        # 1. Fetch pending tasks. Order by retry_count ASC (Priority) to prevent starvation.
        # Filter for PENDING or FAILED (if we want to retry failed ones occasionally)
        candidate_qs = PendingTask.objects.filter(
            status=PendingTask.Status.PENDING
        ).order_by('retry_count', 'created_at')
        
        candidate_ids = list(candidate_qs.values_list('pk', 'retry_count', 'dispatched_at')[:batch_size * 2])
        
        if not candidate_ids: 
            return 0

        # Filter candidates based on exponential backoff
        valid_ids = []
        for pk, retry_count, dispatched_at in candidate_ids:
            if retry_count == 0:
                valid_ids.append(pk)
            else:
                # Exponential backoff: 2^retry_count minutes
                # e.g., 2m, 4m, 8m, 16m...
                backoff_minutes = min(2 ** retry_count, 1440) # Max 24 hours
                last_attempt = dispatched_at or now
                if now >= last_attempt + timezone.timedelta(minutes=backoff_minutes):
                    valid_ids.append(pk)
                    
            if len(valid_ids) >= batch_size:
                break

        if not valid_ids:
            return 0

        # 2. Atomic claim update to prevent multiple workers from picking the same batch
        claimed_count = PendingTask.objects.filter(
            pk__in=valid_ids, status=PendingTask.Status.PENDING
        ).update(status=PendingTask.Status.DISPATCHED, dispatched_at=now)
        
        if claimed_count == 0:
            return 0

        # 3. Retrieve claimed tasks
        claimed_tasks = list(PendingTask.objects.filter(pk__in=valid_ids, status=PendingTask.Status.DISPATCHED))

    success_count = 0
    with app.connection_for_write() as conn:
        conn.connect_timeout = 2.0
        for task in claimed_tasks:
            try:
                app.send_task(
                    task.task_name, 
                    args=task.args, 
                    kwargs=task.kwargs, 
                    queue=task.queue,
                    connection=conn,
                    retry=False
                )
                success_count += 1
            except Exception as e:
                new_retry_count = task.retry_count + 1
                # Dead-Letter Queue: Permanent failure after 15 retries
                new_status = PendingTask.Status.FAILED if new_retry_count >= 15 else PendingTask.Status.PENDING
                PendingTask.objects.filter(pk=task.pk).update(
                    retry_count=new_retry_count,
                    last_error=f"Recovery Error: {str(e)}",
                    status=new_status,
                    dispatched_at=timezone.now()
                )
                logger.error(f"[OUTBOX RECOVERY] Failed to dispatch {task.task_name} (ID: {task.pk}): {str(e)}")
    
    logger.info(f"[OUTBOX RECOVERY] Dispatched {success_count}/{claimed_count} tasks. {claimed_count - success_count} failed and reverted to pending/failed.")
    return success_count

def prune_stale_tasks():
    """
    Cleans up the Outbox to prevent infinite table expansion.
    Removes DISPATCHED tasks older than 3 days.
    """
    from .models import Incident
    
    threshold = timezone.now() - timezone.timedelta(days=3)
    # 1. Clean up successful
    done = PendingTask.objects.filter(status=PendingTask.Status.DISPATCHED, dispatched_at__lt=threshold)
    done_count = done.count()
    done.delete()

    # 2. Clean up permanent failures
    failed_threshold = timezone.now() - timezone.timedelta(days=14)
    failed = PendingTask.objects.filter(status=PendingTask.Status.FAILED, created_at__lt=failed_threshold)
    failed_count = failed.count()
    failed.delete()
    
    if done_count > 0 or failed_count > 0:
        logger.info(f"[OUTBOX PRUNE] Cleaned up {done_count} successful and {failed_count} failed tasks.")
    
    return done_count + failed_count

def check_async_health():
    """
    Returns a health summary of the async infrastructure.
    """
    return {
        "outbox_backlog": PendingTask.objects.filter(status=PendingTask.Status.PENDING).count(),
        "failed_tasks": PendingTask.objects.filter(status=PendingTask.Status.FAILED).count(),
        "critical_retries": PendingTask.objects.filter(retry_count__gt=10).count(),
        "is_healthy": PendingTask.objects.filter(status=PendingTask.Status.PENDING).count() < 100
    }
