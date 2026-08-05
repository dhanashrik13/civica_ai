import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Count, Max
from accounts.models import OfficerProfile, CitizenProfile, User
from issues.models import Issue

logger = logging.getLogger(__name__)

@shared_task(max_retries=3)
def recalculate_officer_metrics(officer_id):
    """
    Async recalculation of officer workload to prevent synchronous DB locks
    on the Issue save path.
    """
    try:
        with transaction.atomic():
            officer = OfficerProfile.objects.select_for_update().get(pk=officer_id)
            active_count = officer.assigned_issues.exclude(status=Issue.Status.RESOLVED).count()
            officer.active_assigned_count = active_count
            
            officer.fatigue_level = min(active_count * 10, 100)
            
            if officer.fatigue_level > 80:
                officer.burnout_risk = 0.8
            elif officer.fatigue_level > 50:
                officer.burnout_risk = 0.3
            else:
                officer.burnout_risk = 0.05
                
            officer.save(update_fields=['active_assigned_count', 'fatigue_level', 'burnout_risk'])
    except OfficerProfile.DoesNotExist:
        logger.warning(f"Officer {officer_id} not found during metric recalculation.")
    except Exception as e:
        logger.error(f"Error recalculating metrics for officer {officer_id}: {e}")

@shared_task(max_retries=3)
def sync_citizen_profile_counters(user_id):
    """
    Async recalculation of citizen report counters to ensure projection safety.
    Strictly synchronizes metadata from the Issue table.
    """
    try:
        with transaction.atomic():
            # Lock the profile to prevent race conditions
            profile = CitizenProfile.objects.select_for_update().get(user_id=user_id)
            
            # Recalculate strictly from Issue table
            stats = Issue.objects.filter(reported_by_id=user_id).aggregate(
                total=Count('id'),
                last_reported=Max('created_at')
            )
            
            actual_total = stats['total'] or 0
            
            profile.total_reports = actual_total
            profile.valid_reports = actual_total  # Assuming all are valid in current schema
            profile.rejected_reports = 0
            profile.spam_reports = 0
            profile.last_reported_at = stats['last_reported']
            
            profile.save(update_fields=[
                'total_reports', 'valid_reports', 
                'rejected_reports', 'spam_reports', 'last_reported_at'
            ])
            logger.info(f"Synchronized counters for CitizenProfile {profile.id} (User {user_id}).")
    except CitizenProfile.DoesNotExist:
        logger.warning(f"CitizenProfile for User {user_id} not found during counter sync.")
    except Exception as e:
        logger.error(f"Error synchronizing counters for CitizenProfile (User {user_id}): {e}")
