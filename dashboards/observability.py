from django.http import JsonResponse
from accounts.models import PendingTask, OfficerProfile, User, AssignmentLog
from issues.models import Issue
from django.utils import timezone
from datetime import timedelta
from final_proj.celery import app

def observability_dashboard_api(request):
    """
    Phase 3: Observability & Operations Dashboard API
    Provides real-time workflow metrics, queue depth, staffing gaps, etc.
    """
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    # 1. Queue Depth & Worker Health
    pending_tasks = PendingTask.objects.filter(status=PendingTask.Status.PENDING)
    failed_tasks = PendingTask.objects.filter(status=PendingTask.Status.FAILED)
    
    queue_metrics = {
        "total_pending": pending_tasks.count(),
        "total_failed": failed_tasks.count(),
        "by_queue": {
            "high_priority": pending_tasks.filter(queue='high_priority').count(),
            "medium_priority": pending_tasks.filter(queue='medium_priority').count(),
            "low_priority": pending_tasks.filter(queue='low_priority').count(),
            "default": pending_tasks.filter(queue='default').count(),
        }
    }

    # Worker health (Try to ping celery)
    try:
        i = app.control.inspect()
        active_workers = i.active() if i else None
        worker_status = "Healthy" if active_workers else "Unreachable"
    except Exception as e:
        worker_status = f"Error: {str(e)}"

    # 2. Assignment Latency (Avg time from created to assigned)
    # Using python to calculate for recent 100 resolved/assigned issues
    recent_assigned = Issue.objects.filter(status__in=[Issue.Status.ASSIGNED, Issue.Status.RESOLVED]).order_by('-created_at')[:100]
    total_seconds = 0
    count = 0
    for issue in recent_assigned:
        log = issue.assignment_logs.first()
        if log:
            diff = (log.assigned_at - issue.created_at).total_seconds()
            total_seconds += diff
            count += 1
            
    avg_assignment_latency = (total_seconds / count) if count > 0 else 0

    # 3. Staffing Gap Heatmap (Departments with most pending issues but fewest active officers)
    from django.db.models import Count, Q
    from accounts.models import Department
    
    depts = Department.objects.annotate(
        pending_issues=Count('issues', filter=Q(issues__status=Issue.Status.PENDING)),
        active_officers=Count('officer_profiles', filter=Q(officer_profiles__is_active=True))
    )
    
    staffing_gaps = []
    for d in depts:
        ratio = (d.pending_issues / d.active_officers) if d.active_officers > 0 else d.pending_issues
        if ratio > 5: # Arbitrary threshold for "gap"
            staffing_gaps.append({
                "department": d.name,
                "pending": d.pending_issues,
                "officers": d.active_officers,
                "load_ratio": round(ratio, 2)
            })

    # 4. Failed Assignment Audit Logs (Issues stuck in pending for > 24h)
    stuck_threshold = timezone.now() - timedelta(days=1)
    stuck_issues = Issue.objects.filter(status=Issue.Status.PENDING, created_at__lt=stuck_threshold).count()

    return JsonResponse({
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "queue_metrics": queue_metrics,
        "worker_status": worker_status,
        "avg_assignment_latency_seconds": round(avg_assignment_latency, 2),
        "stuck_issues_24h": stuck_issues,
        "staffing_gaps_heatmap": sorted(staffing_gaps, key=lambda x: x['load_ratio'], reverse=True)
    })
