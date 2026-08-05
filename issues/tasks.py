import logging
from celery import shared_task
from django.utils import timezone
from final_proj.celery import DLQTask
from issues.models import Issue

logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    base=DLQTask, 
    max_retries=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=60,
    soft_time_limit=30
)
def scan_and_escalate_issues(self):
    """
    Scans for overdue issues and triggers deterministic escalations.
    Reassigns issues to higher-level officers if available.
    ENFORCES AUTHORITY FENCES & DEGRADED MODE.
    """
    from accounts.models import OfficerProfile, AuditLog, PendingTask
    from .utils import find_best_officer
    from notifications.models import Notification
    from accounts.middleware import bypass_rbac
    
    # DEGRADED MODE CHECK: Do not automate governance decisions if system is heavily lagging
    backlog_count = PendingTask.objects.filter(status=PendingTask.Status.PENDING).count()
    if backlog_count > 1000:
        logger.warning(f"DEGRADED MODE: Escalation halted due to high outbox backlog ({backlog_count}). Preventing split-brain governance.")
        return False

    # Bounded query to 100 issues per run to prevent timeout/lock congestion
    # AUTHORITY FENCE: Exclude manual_override issues
    issues_qs = Issue.objects.exclude(status=Issue.Status.RESOLVED).exclude(manual_override=True).select_related(
        'assigned_to', 'assigned_to__user', 'department'
    ).order_by('created_at')[:100]
    
    escalated_count = 0
    for issue in issues_qs:
        if issue.is_overdue:
            old_officer = issue.assigned_to

            
            # DETERMINISTIC ESCALATION LOGIC
            # Try to find a higher level officer
            new_officer = None
            
            if old_officer:
                # Search for officers at a higher level in same dept/geography
                higher_levels = []
                if old_officer.level in ['village', 'ward']:
                    higher_levels = ['taluka', 'zone', 'city', 'district']
                elif old_officer.level in ['taluka', 'zone', 'city']:
                    higher_levels = ['district']
                
                if higher_levels:
                    # Find best among higher levels
                    from django.db.models import Count, Q
                    candidates = OfficerProfile.objects.filter(
                        department=issue.department,
                        district=issue.district,
                        level__in=higher_levels,
                        is_active=True
                    ).annotate(
                        active_workload=Count('assigned_issues', filter=~Q(assigned_issues__status='resolved'))
                    ).order_by('level', 'active_workload')
                    
                    if candidates.exists():
                        new_officer = candidates.first()

            # If no specific higher officer found, or wasn't assigned, use standard assignment with escalation flag
            if not new_officer:
                # find_best_officer will already try stages, but we want to ensure it doesn't just pick the same one
                new_officer = find_best_officer(issue)
            
            if new_officer and new_officer != old_officer:
                from .services import secure_issue_assignment
                secure_issue_assignment(issue, new_officer, assigned_by=None)
                
                # Update explanation after secure assignment (which saves)
                issue.refresh_from_db()
                issue.assignment_explanation += f" | ESCALATED due to SLA violation (Old: {old_officer.user.username if old_officer else 'None'})"
                # We can use bypass_rbac here to avoid re-triggering signals if necessary
                with bypass_rbac():
                    issue.save(update_fields=['assignment_explanation'])
                
                # Notify new officer
                from notifications.tasks import dispatch_notifications
                dispatch_notifications.delay(
                    new_officer.user.id,
                    Notification.Type.ESCALATION,
                    f"ESCALATION ALERT: Issue #{issue.id} ('{issue.title}') has been escalated to you!",
                    related_issue_id=issue.id,
                    channels=[Notification.Channel.IN_APP, Notification.Channel.SMS]
                )
                
            escalated_count += 1
            
    logger.info(f"Scanned and processed {escalated_count} overdue issues.")
    return escalated_count


@shared_task(
    bind=True, 
    base=DLQTask, 
    max_retries=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600, # 1 hour max backoff
    retry_jitter=True,
    time_limit=120,
    soft_time_limit=60
)
def enrich_issue_context(self, issue_id):
    """
    Asynchronously enriches an issue with geo-traversal and AI risk analysis.
    Offloads heavy processing from Issue.save() for massive scalability (WP-C2).
    """
    from issues.models import Issue
    from accounts.models import Location
    from .utils import calculate_adaptive_risk
    from accounts.middleware import bypass_rbac
    from ai.intelligence import get_intel_engine
    
    try:
        issue = Issue.objects.select_related(
            'reported_by', 
            'location__parent__parent__parent'
        ).get(pk=issue_id)
        
        # 1. CENTRALIZED GEO-SYNC (Simplification Pass)
        from accounts.services import LocationService
        hierarchy = LocationService.resolve_hierarchy(issue.location)
        issue.district = hierarchy['district']
        issue.taluka = hierarchy['taluka']
        issue.village = hierarchy['village']
        issue.city = hierarchy['city']
        issue.zone = hierarchy['zone']
        issue.ward = hierarchy['ward']
        
        # 2. SLA PRE-COMPUTATION (N+1 Mitigation - WP-H1)
        from accounts.models import DistrictOperationalCondition
        active_conditions = DistrictOperationalCondition.objects.filter(
            district__name__iexact=issue.district,
            is_active=True
        )
        multiplier = 1.0
        for cond in active_conditions:
            multiplier = max(multiplier, cond.sla_multiplier)
        issue.sla_multiplier = multiplier

        # 3. RISK CALCULATION
        from .utils import calculate_adaptive_risk
        calculate_adaptive_risk(issue)
        
        # 4. FRAUD DETECTION
        from ai.intelligence import get_intel_engine
        engine = get_intel_engine()
        fraud_data = engine.detect_governance_fraud(issue.reported_by, issue)
        
        # Merge fraud data into intelligence_data
        intel_data = issue.intelligence_data or {}
        intel_data['fraud_analysis'] = fraud_data
        issue.intelligence_data = intel_data
        
        # 4. EMBEDDING PERSISTENCE (Optimization)
        from issues.models import IssueEmbedding
        embedding_vector = engine.ai.get_embedding(f"{issue.title} {issue.description}")
        if embedding_vector:
            IssueEmbedding.objects.update_or_create(
                issue=issue,
                defaults={'vector': embedding_vector}
            )

        # 5. AUTO-ASSIGNMENT TRIGGER
        from .services import auto_assign_issue
        logger.info(f"[ENRICHMENT] Triggering auto-assignment for Issue #{issue_id}")
        auto_assign_issue(issue)

        issue.is_enriched = True
        
        # Use bypass_rbac to ensure we don't trigger more tasks or RBAC checks
        with bypass_rbac():
            # Concrete fields only for update_fields
            issue.save(update_fields=[
                'district', 'taluka', 'village', 'city', 'zone', 'ward',
                'department', 'assigned_to', 'status'
            ])
            
        logger.info(f"[ENRICHMENT] Successfully processed issue #{issue_id}. Assigned To: {issue.assigned_to}")
        return True
        
    except Issue.DoesNotExist:
        logger.warning(f"[ENRICHMENT] Issue #{issue_id} not found.")
        return False
    except Exception as exc:
        logger.error(f"[ENRICHMENT] Failed for issue #{issue_id}: {str(exc)}")
        # Raise exc to trigger autoretry_for
        raise exc

@shared_task(
    bind=True, 
    base=DLQTask, 
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True
)
def update_dashboard_projections(self, event_id):
    """
    Async projection task to update denormalized read models from the event stream.
    """
    from .projections import process_issue_event
    try:
        process_issue_event(event_id)
        return True
    except Exception as exc:
        logger.error(f"[PROJECTION] Failed for event {event_id}: {str(exc)}")
        raise self.retry(exc=exc, countdown=10)

@shared_task
def process_heavy_chaos_load(iterations=1000000):
    """CPU intensive task for chaos stress testing"""
    result = 0
    for i in range(iterations):
        result += i
    return result
