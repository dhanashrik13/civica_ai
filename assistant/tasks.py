import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from assistant.services import _execute_sequenced_action, send_to_monitoring_service
from assistant.models import AIActionLog

User = get_user_model()
logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5, # 5 seconds delay between retries
    queue='high_priority'
)
def execute_ai_action_task(self, user_id, action_token, session_hash):
    """
    Background worker task for executing validated AI actions.
    Includes automatic retries with exponential backoff.
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Update log status to processing
        AIActionLog.objects.filter(action_token=action_token).update(status="processing")
        
        result = _execute_sequenced_action(user, action_token, session_hash=session_hash)
        
        if not result.get("success"):
            # If the failure is retryable (like DB deadlock), we retry
            error_code = result.get("error_code")
            if error_code == "DB_DEADLOCK":
                raise self.retry(exc=Exception("Database deadlock encountered"))
            
            # For other failures, we log and complete with failure
            send_to_monitoring_service("task_failure", {"user_id": user_id, "token": action_token, "result": result})
            return result
            
        return result

    except User.DoesNotExist:
        return {"success": False, "message": "User not found during background task."}
    except Exception as exc:
        # Unexpected errors trigger retries
        logger.exception(f"Unexpected error in background task for {action_token}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)
        
        AIActionLog.objects.filter(action_token=action_token).update(
            status="failed", 
            error_message=f"Task failed after retries: {str(exc)}"
        )
        return {"success": False, "message": "Maximum retries reached. Action failed."}
