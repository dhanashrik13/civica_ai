from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import Count, Q

from .models import Issue, Comment, EscalationAppeal
from notifications.services import create_notification
from notifications.models import Notification
from accounts.utils_async import dispatch_task_transactional
from accounts.middleware import is_forensic_mode
from accounts.models import OfficerProfile

@receiver(post_save, sender=EscalationAppeal)
def handle_appeal_notifications(sender, instance, created, **kwargs):
    """
    Notifies relevant parties when an escalation appeal is created or updated.
    """
    if is_forensic_mode(): return

    if created:
        # Notify admins? (Actually we'll notify the reporting citizen first as confirmation)
        create_notification(
            instance.citizen_id, Notification.Type.ESCALATION,
            f"Appeal Filed: Your appeal for Issue #CN-{instance.issue_id} has been submitted for review.",
            related_issue_id=instance.issue_id,
            channels=[Notification.Channel.IN_APP]
        )
    else:
        # Notify citizen of status change
        create_notification(
            instance.citizen_id, Notification.Type.ESCALATION,
            f"Appeal Update: Your appeal for Issue #CN-{instance.issue_id} is now {instance.get_status_display()}.",
            related_issue_id=instance.issue_id,
            channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL]
        )

@receiver(post_save, sender=Issue)
@receiver(post_delete, sender=Issue)
def update_citizen_counters(sender, instance, **kwargs):
    """
    Updates citizen report counters when an issue is created, modified, or deleted.
    DEFERRED TO ASYNC OUTBOX for projection safety and idempotency.
    """
    if is_forensic_mode(): return
    if instance.reported_by_id:
        dispatch_task_transactional('accounts.tasks.sync_citizen_profile_counters', args=[instance.reported_by_id])

@receiver(post_save, sender=Issue)
def update_officer_metrics(sender, instance, **kwargs):
    """
    Updates operational metrics for officers when an issue is assigned or resolved.
    DEFERRED TO ASYNC OUTBOX to eliminate select_for_update lock contention on the hot path.
    """
    if is_forensic_mode(): return

    officers_to_update = set()
    if instance.assigned_to_id:
        officers_to_update.add(instance.assigned_to_id)
    
    # Track reassignment to update old officer
    if hasattr(instance, '_old_assigned_to_id'):
        if instance._old_assigned_to_id:
            officers_to_update.add(instance._old_assigned_to_id)

    for officer_id in officers_to_update:
        dispatch_task_transactional('accounts.tasks.recalculate_officer_metrics', args=[officer_id])

@receiver(post_save, sender=Issue)
def handle_issue_notifications(sender, instance, created, **kwargs):
    """
    Centralized signal handler for Issue-related notifications.
    Now creates record synchronously for LIVE in-app experience.
    """
    if is_forensic_mode():
        return # Suppress side-effects during replay
    
    if created:
        # 1. Issue Created Notification (To Citizen)
        if instance.reported_by_id:
            create_notification(
                instance.reported_by_id, Notification.Type.ISSUE_CREATED, 
                f"Your issue #CN-{instance.id} '{instance.title}' has been reported successfully.",
                related_issue_id=instance.id,
                channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL],
                severity=Notification.Severity.LOW
            )
    else:
        # 2. Issue Assigned Notification (To Officer)
        if instance.status == Issue.Status.ASSIGNED and instance.assigned_to:
            severity = Notification.Severity.MEDIUM
            if instance.priority == Issue.Priority.HIGH: severity = Notification.Severity.HIGH
            if instance.priority == Issue.Priority.EMERGENCY: severity = Notification.Severity.CRITICAL

            create_notification(
                instance.assigned_to.user_id, Notification.Type.ISSUE_ASSIGNED,
                f"New task: Issue #CN-{instance.id} '{instance.title}' has been assigned to you.",
                related_issue_id=instance.id,
                channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL, Notification.Channel.SMS],
                severity=severity
            )

        # 3. Issue Resolved Notification (To Citizen)
        if instance.status == Issue.Status.RESOLVED and instance.reported_by_id:
            create_notification(
                instance.reported_by_id, Notification.Type.ISSUE_RESOLVED,
                f"🎉 Success! Your issue #CN-{instance.id} '{instance.title}' has been resolved.",
                related_issue_id=instance.id,
                channels=[Notification.Channel.IN_APP, Notification.Channel.EMAIL]
            )
        
        # 4. Status Update (To Citizen)
        elif instance.status != Issue.Status.PENDING and instance.reported_by_id:
             create_notification(
                instance.reported_by_id, Notification.Type.ISSUE_UPDATED,
                f"Status Update: Issue #CN-{instance.id} '{instance.title}' is now {instance.get_status_display()}.",
                related_issue_id=instance.id, 
                channels=[Notification.Channel.IN_APP]
            )

@receiver(post_save, sender=Comment)
def handle_comment_notifications(sender, instance, created, **kwargs):
    """
    Notifies relevant parties when a new comment is added.
    """
    if not created or is_forensic_mode(): return

    issue = instance.issue
    
    # If officer comments -> Notify citizen
    if instance.user.role == 'officer' and issue.reported_by_id:
        create_notification(
            issue.reported_by_id, Notification.Type.ISSUE_UPDATED,
            f"Officer {instance.user.username} commented on your issue #CN-{issue.id}.",
            related_issue_id=issue.id,
            channels=[Notification.Channel.IN_APP]
        )
    
    # If citizen comments -> Notify assigned officer
    elif instance.user.role == 'citizen' and issue.assigned_to:
        create_notification(
            issue.assigned_to.user_id, Notification.Type.ISSUE_UPDATED,
            f"Citizen {instance.user.username} commented on assigned issue #CN-{issue.id}.",
            related_issue_id=issue.id,
            channels=[Notification.Channel.IN_APP]
        )
