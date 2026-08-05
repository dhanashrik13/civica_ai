import logging
from celery import shared_task
from django.utils import timezone
from .models import Notification
from final_proj.celery import DLQTask

logger = logging.getLogger(__name__)

@shared_task(bind=True, base=DLQTask, max_retries=5)
def send_notification_task(self, notification_id):
    """
    Asynchronously delivers a notification through the specified channel.
    """
    try:
        notification = Notification.objects.select_related('user').get(pk=notification_id)
        
        # Simulate channel-specific logic
        if notification.channel == Notification.Channel.EMAIL:
            # Mock email sending logic
            logger.info(f"Sending Email to {notification.user.email}: {notification.message}")
            # if fail: raise Exception("Email gateway timeout")
            
        elif notification.channel == Notification.Channel.SMS:
            # Mock SMS sending logic
            logger.info(f"Sending SMS to {notification.user.phone_no}: {notification.message}")
            
        # In-App is handled by just creating the record (which is already done)
        
        notification.delivery_status = 'delivered'
        notification.delivered_at = timezone.now()
        notification.save()
        
        return True
    except Exception as exc:
        notification = Notification.objects.get(pk=notification_id)
        notification.retry_count += 1
        notification.error_log = str(exc)
        notification.delivery_status = 'failed'
        notification.save()
        
        logger.error(f"Failed to send notification {notification_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * notification.retry_count)

@shared_task
def dispatch_notifications(user_id, type, message, related_issue_id=None, channels=None, idempotency_key=None, severity=Notification.Severity.MEDIUM):
    """
    Async wrapper for create_notification service.
    Maintained for backward compatibility with existing task calls.
    """
    from .services import create_notification
    return create_notification(
        user_id=user_id,
        n_type=type,
        message=message,
        related_issue_id=related_issue_id,
        channels=channels,
        severity=severity,
        idempotency_key=idempotency_key
    )
