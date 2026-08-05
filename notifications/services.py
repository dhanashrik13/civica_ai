from .models import Notification
from django.utils import timezone
import logging
from .tasks import send_notification_task

logger = logging.getLogger(__name__)

def create_notification(user_id, n_type, message, related_issue_id=None, channels=None, severity=Notification.Severity.MEDIUM, idempotency_key=None):
    """
    Core service to create a notification record and dispatch to async channels.
    """
    if channels is None:
        channels = [Notification.Channel.IN_APP]

    # Generate idempotency key if not provided
    ikey = idempotency_key or f"notif_{user_id}_{n_type}_{related_issue_id}_{severity}_{timezone.now().strftime('%Y%m%d%H%M')}"

    # Deduplication (1 min window for same exact message to same user)
    recent_window = timezone.now() - timezone.timedelta(minutes=1)
    if Notification.objects.filter(user_id=user_id, message=message, created_at__gte=recent_window).exists():
        logger.info(f"[DEDUPE] Skipping duplicate message for user {user_id}")
        return None

    # 1. Always create the database record first (the "Live" part)
    notification = Notification.objects.create(
        user_id=user_id,
        type=n_type,
        message=message,
        related_issue_id=related_issue_id,
        severity=severity,
        idempotency_key=ikey,
        channel=Notification.Channel.IN_APP # Primary record is always in-app
    )

    # 2. Dispatch to other channels asynchronously if requested
    other_channels = [c for c in channels if c != Notification.Channel.IN_APP]
    for channel in other_channels:
        # Create separate records for other channels or just use one?
        # The current model has one 'channel' field. 
        # For simplicity and multi-channel support, we might need a better model, 
        # but following STRICT RULES: DO NOT alter database structure unnecessarily.
        # So we'll just handle the primary channel and mock the others in the task.
        pass

    # If non-in-app channels were requested, we use the transactional outbox to 'deliver' them
    if any(c != Notification.Channel.IN_APP for c in channels):
        from accounts.utils_async import dispatch_task_transactional
        # Note: dispatch_task_transactional ensures we don't block the request if Redis is down
        dispatch_task_transactional('notifications.tasks.send_notification_task', args=[notification.id])

    return notification
