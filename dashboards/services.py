from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField, Value, Case, When, FloatField
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, OfficerProfile, Location, Department, AssignmentLog
from accounts.utils import apply_rbac_filter
from issues.models import Issue, Comment
from dashboards.models import Announcement

def get_issue_counts(user):
    from issues.projections import is_projection_stale
    from dashboards.models import DistrictDashboardProjection

    # Try to use fast read model if user is bounded by district/dept
    # (e.g., DEPT_ADMIN or specific OFFICER).
    # For SUPER_ADMIN global view, we might still need live aggregation or global projection.
    if hasattr(user, 'admin_profile') and user.admin_profile.department and user.admin_profile.district:
        district = user.admin_profile.district
        department = user.admin_profile.department
        
        # DEGRADED MODE CHECK: Is projection safe to read?
        if not is_projection_stale(district, department, max_lag_seconds=30):
            try:
                proj = DistrictDashboardProjection.objects.get(district=district, department=department)
                return {
                    "total": proj.pending_count + proj.assigned_count + proj.resolved_count,
                    "pending": proj.pending_count,
                    "assigned": proj.assigned_count,
                    "resolved": proj.resolved_count,
                    "critical": proj.high_priority_count,
                    "source": "projection" # Telemetry
                }
            except DistrictDashboardProjection.DoesNotExist:
                pass
        else:
            import logging
            logging.getLogger(__name__).warning(f"DEGRADED MODE: Projection stale for {district}/{department}. Falling back to live Issue table.")

    # FALLBACK: Direct source-of-truth read (Strong Consistency but slower)
    qs = apply_rbac_filter(Issue.objects.all(), user)
    return {
        "total": qs.count(),
        "pending": qs.filter(status=Issue.Status.PENDING).count(),
        "assigned": qs.filter(status=Issue.Status.ASSIGNED).count(),
        "resolved": qs.filter(status=Issue.Status.RESOLVED).count(),
        "critical": qs.filter(priority=Issue.Priority.HIGH).count(),
        "source": "live_db" # Telemetry
    }

def get_time_series(user, days=30):
    qs = apply_rbac_filter(Issue.objects.all(), user)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    reported = qs.filter(created_at__date__gte=start_date).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(count=Count('id')).order_by('date')
    
    resolved = qs.filter(status=Issue.Status.RESOLVED, resolved_at__date__gte=start_date).annotate(
        date=TruncDate('resolved_at')
    ).values('date').annotate(count=Count('id')).order_by('date')
    
    # Fill gaps with 0
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    reported_dict = {item['date']: item['count'] for item in reported}
    resolved_dict = {item['date']: item['count'] for item in resolved}
    
    return {
        "labels": [d.strftime("%b %d") for d in date_range],
        "reported": [reported_dict.get(d, 0) for d in date_range],
        "resolved": [resolved_dict.get(d, 0) for d in date_range]
    }

def get_critical_issues(user, limit=5):
    qs = apply_rbac_filter(Issue.objects.all(), user)
    return qs.filter(priority=Issue.Priority.HIGH).exclude(status=Issue.Status.RESOLVED).order_by('-created_at')[:limit]

def get_map_points(user):
    qs = apply_rbac_filter(Issue.objects.all(), user).exclude(latitude__isnull=True, longitude__isnull=True)
    return list(qs.values('id', 'title', 'latitude', 'longitude', 'status', 'priority', 'category'))

def get_trending_issues(user, limit=5, department=None):
    qs = apply_rbac_filter(Issue.objects.all(), user)
    
    if department:
        qs = qs.filter(department=department)
    
    # First try: high priority issues not resolved
    trending = qs.filter(priority=Issue.Priority.HIGH).exclude(status=Issue.Status.RESOLVED).order_by('-created_at')[:limit]
    
    # Fallback 1: If no high priority, get any non-resolved issues
    if not trending.exists():
        trending = qs.exclude(status=Issue.Status.RESOLVED).order_by('-created_at')[:limit]
        
    # Fallback 2: If still empty (everything resolved or no data), get latest 5 regardless of status
    if not trending.exists():
        trending = qs.order_by('-created_at')[:limit]
        
    # Fallback 3: For admin only, if RBAC returns nothing but DB has data, show all
    if not trending.exists() and (user.is_superuser or user.role == "super_admin"):
        trending = Issue.objects.all()
        if department:
            trending = trending.filter(department=department)
        trending = trending.order_by('-created_at')[:limit]
        
    return trending

def get_activity_feed(user, limit=10):
    # This should combine various activities
    activities = []
    
    # 1. Recent Issues (New reports) - STRICT CITIZEN FILTER
    issues = apply_rbac_filter(Issue.objects.all(), user).filter(
        reported_by__role=User.Role.CITIZEN
    ).exclude(
        Q(reported_by__username__icontains="officer") | 
        Q(reported_by__username__icontains="admin")
    ).order_by('-created_at')[:limit]
    
    for issue in issues:
        activities.append({
            'title': f"New Issue: {issue.title}",
            'description': f"Reported in {issue.location}",
            'time': issue.created_at,
            'icon': 'bi bi-plus-circle-fill',
            'type': 'issue'
        })
        
    # 2. Recent Comments - STRICT CITIZEN FILTER
    comments = apply_rbac_filter(Comment.objects.all(), user).select_related('issue', 'user').filter(
        user__role=User.Role.CITIZEN
    ).exclude(
        Q(user__username__icontains="officer") | 
        Q(user__username__icontains="admin")
    ).order_by('-created_at')[:limit]
    
    for comment in comments:
        activities.append({
            'title': f"New Comment by {comment.user.username}",
            'description': f"On issue: {comment.issue.title}",
            'time': comment.created_at,
            'icon': 'bi bi-chat-left-text-fill',
            'type': 'comment'
        })
        
    # Sort by time and limit
    activities.sort(key=lambda x: x['time'], reverse=True)
    
    # Debug verification
    print(f"DEBUG: Activity Feed items: {[a['title'] for a in activities[:5]]}")
    
    return activities[:limit]

def get_active_citizens(user, limit=5, department=None):
    """
    Returns top active citizens grouped by department.
    Output: [{'department': dept_obj, 'citizens': [...]}, ...]
    """
    from django.db.models import Max, Count
    
    # 1. Base Queryset (Citizen reports only)
    citizen_issues = apply_rbac_filter(Issue.objects.all(), user).filter(
        reported_by__role=User.Role.CITIZEN
    ).exclude(
        Q(reported_by__username__icontains="officer") | 
        Q(reported_by__username__icontains="admin")
    )
    
    if department:
        citizen_issues = citizen_issues.filter(department=department)

    # 2. Get distinct departments involved
    dept_ids = citizen_issues.values_list('department', flat=True).distinct()
    depts = Department.objects.filter(id__in=dept_ids).order_by('name')

    results = []
    for dept in depts:
        # Get top citizens for THIS department
        citizens = citizen_issues.filter(department=dept).values(
            'reported_by__id', 
            'reported_by__username', 
            'reported_by___legacy_full_name'
        ).annotate(
            report_count=Count('id'),
            last_activity=Max('created_at')
        ).order_by('-report_count')[:limit]
        
        if citizens:
            results.append({
                'department': dept,
                'citizens': list(citizens)
            })
            
    return results

def paginate_queryset(queryset, page_number, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)

def get_citizen_dashboard_context(user):
    # Option A: Delete expired announcements before fetching
    Announcement.objects.filter(expires_at__lt=timezone.now()).delete()

    reports_qs = apply_rbac_filter(Issue.objects.all(), user)
    total_count = reports_qs.count()
    resolved_count = reports_qs.filter(status=Issue.Status.RESOLVED).count()
    
    # Nearby issues (simplified: all issues the user can see for now, 
    # but could be filtered by user's location if available)
    nearby_issues = Issue.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)[:10]

    return {
        "total_issues": total_count,
        "resolved_issues": resolved_count,
        "pending_issues": reports_qs.filter(status=Issue.Status.PENDING).count(),
        "resolution_rate": round((resolved_count / total_count * 100), 1) if total_count > 0 else 0,
        "nearby_count": nearby_issues.count(),
        "issues": reports_qs.order_by("-created_at")[:5],
        "nearby_issues": nearby_issues,
        "announcements": Announcement.objects.filter(is_approved=True, expires_at__gt=timezone.now()),
        "departments": Department.objects.annotate(
            total=Count('issues'), # Total in dept (visible to citizen)
            resolved=Count('issues', filter=Q(issues__status=Issue.Status.RESOLVED)),
            pending=Count('issues', filter=Q(issues__status=Issue.Status.PENDING))
        ).filter(total__gt=0)
    }

def get_citizen_reports_context(user, status_filter=None, page_number=1):
    reports_qs = apply_rbac_filter(Issue.objects.all(), user).order_by("-created_at")
    if status_filter:
        reports_qs = reports_qs.filter(status=status_filter)
    
    page_obj = paginate_queryset(reports_qs, page_number)
    return {
        "reports": page_obj.object_list,
        "page_obj": page_obj,
        "status_filter": status_filter,
    }

def get_officer_dashboard_context(user, filters=None, page_number=1):
    issues_qs = apply_rbac_filter(Issue.objects.all(), user)
    
    if filters:
        if filters.get("search"):
            issues_qs = issues_qs.filter(Q(title__icontains=filters["search"]) | Q(id__icontains=filters["search"]))
        if filters.get("priority"):
            issues_qs = issues_qs.filter(priority=filters["priority"])
        if filters.get("status"):
            issues_qs = issues_qs.filter(status=filters["status"])
            
    # Stats
    total = issues_qs.count()
    resolved = issues_qs.filter(status=Issue.Status.RESOLVED).count()
    pending = issues_qs.filter(status=Issue.Status.PENDING).count()
    
    page_obj = paginate_queryset(issues_qs.order_by("-created_at"), page_number)
    
    # Human Governance: Operational Metrics
    officer_profile = getattr(user, 'officer', None)
    pressure_info = {
        "level": 0,
        "status": "Unknown",
        "fatigue": 0,
        "burnout_risk": 0.0
    }
    if officer_profile:
        pressure_info = {
            "level": officer_profile.pressure_level,
            "status": officer_profile.pressure_status,
            "fatigue": officer_profile.fatigue_level,
            "burnout_risk": officer_profile.burnout_risk
        }

    return {
        "issues": page_obj.object_list,
        "page_obj": page_obj,
        "total_issues": total,
        "assigned_issues": total, # For an officer, all issues they see are assigned to them
        "resolved": resolved,
        "in_progress": issues_qs.filter(status=Issue.Status.ASSIGNED).count(),
        "pending": pending,
        "completion_rate": int((resolved / total * 100)) if total > 0 else 0,
        "stats": {
            "total": total,
            "resolved": resolved,
            "pending": pending,
            "completion_rate": int((resolved / total * 100)) if total > 0 else 0
        },
        "pressure": pressure_info,
        "officer": officer_profile
    }

from django.db.models import Q, Avg, Count, F, ExpressionWrapper, DurationField
from django.utils import timezone
from accounts.models import User
from issues.models import Issue, Department
from accounts.utils import apply_rbac_filter


def get_admin_dashboard_context(user, issues_queryset=None):
    # ----------------------------------------
    # SINGLE SOURCE OF TRUTH (IMPORTANT)
    # ----------------------------------------
    if issues_queryset is None:
        issues_queryset = apply_rbac_filter(Issue.objects.all(), user)

    qs = issues_queryset

    today = timezone.now().date()

    # ----------------------------------------
    # TOTAL ISSUES (RBAC SAFE)
    # ----------------------------------------
    total_issues = qs.count()

    # ----------------------------------------
    # ACTIVE = NOT resolved / closed
    # ----------------------------------------
    active_qs = qs.exclude(
        Q(status__iexact="resolved") |
        Q(status__iexact="closed")
    )
    active_issues = active_qs.count()

    # ----------------------------------------
    # CRITICAL = HIGH PRIORITY + ACTIVE ONLY
    # ----------------------------------------
    critical_issues = active_qs.filter(
        priority__iexact="high"
    ).count()

    # ----------------------------------------
    # RESOLVED TODAY
    # ----------------------------------------
    resolved_today = qs.filter(
        status__iexact="resolved",
        updated_at__date=today
    ).count()

    # ----------------------------------------
    # RESOLUTION RATE
    # ----------------------------------------
    resolved_count = qs.filter(
        Q(status__iexact="resolved") |
        Q(status__iexact="closed")
    ).count()

    resolution_rate = (
        (resolved_count / total_issues) * 100
        if total_issues > 0 else 0
    )

    # ----------------------------------------
    # ADDITIONAL STATS
    # ----------------------------------------
    pending_issues = qs.filter(status__iexact="pending").count()
    assigned_issues = qs.filter(status__iexact="assigned").count()
    warning_issues = qs.filter(priority__iexact="medium").count()
    resolved_issues = qs.filter(status__iexact="resolved").count()

    # ----------------------------------------
    # AVG RESPONSE TIME
    # ----------------------------------------
    avg_res = qs.filter(
        status__iexact="resolved",
        resolved_at__isnull=False
    ).annotate(
        duration=ExpressionWrapper(
            F('resolved_at') - F('created_at'),
            output_field=DurationField()
        )
    ).aggregate(avg=Avg('duration'))['avg']

    avg_hours = int(avg_res.total_seconds() / 3600) if avg_res else 0

    # ----------------------------------------
    # TOTAL CITIZENS (GLOBAL - OK)
    # ----------------------------------------
    total_citizens = User.objects.filter(
        role=User.Role.CITIZEN
    ).count()

    # ----------------------------------------
    # DEPARTMENT BREAKDOWN (RBAC SAFE)
    # ----------------------------------------
    departments = Department.objects.annotate(
        total=Count('issues', filter=Q(issues__id__in=qs.values('id'))),
        resolved=Count('issues', filter=Q(
            issues__id__in=qs.values('id'),
            issues__status__iexact="resolved"
        )),
        pending=Count('issues', filter=Q(
            issues__id__in=qs.values('id'),
            issues__status__iexact="pending"
        ))
    ).filter(total__gt=0)

    # ----------------------------------------
    # DEBUG (DON'T REMOVE UNTIL STABLE)
    # ----------------------------------------
    print("TOTAL:", total_issues)
    print("ACTIVE:", active_issues)
    print("CRITICAL:", critical_issues)
    print("RESOLVED TODAY:", resolved_today)
    print("RESOLUTION RATE:", round(resolution_rate, 2))

    # ----------------------------------------
    # HUMAN GOVERNANCE: PRESSURE & READINESS
    # ----------------------------------------
    all_officers = apply_rbac_filter(OfficerProfile.objects.all(), user)
    avg_pressure = all_officers.aggregate(avg=Avg(F('fatigue_level') + F('active_assigned_count') * 5))['avg'] or 0
    avg_pressure = min(int(avg_pressure), 100)
    
    # Critical Districts (Districts with high pressure)
    critical_districts = []
    # Conceptual: This would group by district and find high pressure ones
    # For now, let's just use the avg_pressure as a global indicator
    
    # ----------------------------------------
    # FINAL CONTEXT
    # ----------------------------------------
    return {
        "total_issues": total_issues,
        "active_issues": active_issues,
        "critical_issues": critical_issues,
        "resolved_today": resolved_today,
        "resolution_rate": round(resolution_rate, 2),

        "total_count": total_issues,
        "resolved_issues": resolved_issues,
        "pending_issues": pending_issues,
        "assigned_issues": assigned_issues,
        "warning_issues": warning_issues,

        "total_citizens": total_citizens,
        "avg_response_hours": avg_hours,
        "efficiency_rate": round(resolution_rate, 2),

        "departments": departments,
        "avg_district_pressure": avg_pressure,
        "governance_health": "Stable" if avg_pressure < 50 else ("Warning" if avg_pressure < 80 else "Critical")
    }

def get_global_search_context(query, user):
    # Base querysets with RBAC filtering
    issues_base = apply_rbac_filter(Issue.objects.all(), user)
    users_base = apply_rbac_filter(User.objects.all(), user)
    officers_base = apply_rbac_filter(OfficerProfile.objects.all(), user)
    
    issues = issues_base.filter(Q(title__icontains=query) | Q(metadata__description__icontains=query) | Q(id__icontains=query))
    users = users_base.filter(Q(username__icontains=query) | Q(_legacy_full_name__icontains=query))
    officers = officers_base.filter(Q(user__username__icontains=query) | Q(user___legacy_full_name__icontains=query))
    
    return {
        "query": query,
        "issues": issues[:10],
        "users": users[:10],
        "officers": officers[:10],
        "total_results": issues.count() + users.count() + officers.count()
    }

def get_officer_performance_stats(user, issues_queryset=None, department=None):
    """
    Calculates performance stats for officers using efficient ORM annotations.
    Metric: Efficiency = (completed_tasks / assigned_tasks) * 100
    Sorting: Efficiency DESC, completed_count DESC
    """
    # 1. Base Queryset
    officers_qs = OfficerProfile.objects.select_related("user", "department")

    # 2. Apply Department Filter if provided
    if department:
        officers_qs = officers_qs.filter(department=department)

    # 3. RBAC Filtering (Optional, based on user role)
    if user and not user.is_superuser and user.role != "super_admin":
        admin_profile = getattr(user, 'admin_profile', None)
        if admin_profile and admin_profile.department:
            officers_qs = officers_qs.filter(department=admin_profile.department)

    # 4. Annotate with Metrics using Subqueries to prevent join-induced row multiplication
    from django.db.models import Subquery, OuterRef
    
    assigned_sq = Issue.objects.filter(assigned_to=OuterRef('pk'))
    completed_sq = assigned_sq.filter(status=Issue.Status.RESOLVED)
    pending_sq = assigned_sq.exclude(status=Issue.Status.RESOLVED)
    
    # For escalations, we check if ANY domain event of type 'escalated' exists for issues assigned to this officer
    from issues.models import IssueEvent
    escalated_issues_ids = IssueEvent.objects.filter(
        issue__assigned_to=OuterRef('pk'), 
        event_type=IssueEvent.Type.ESCALATED
    ).values('issue_id').distinct()

    officers_qs = officers_qs.annotate(
        assigned_count=Count('assigned_issues', distinct=True),
        completed_count=Count('assigned_issues', filter=Q(assigned_issues__status=Issue.Status.RESOLVED), distinct=True),
        pending_count=Count('assigned_issues', filter=~Q(assigned_issues__status=Issue.Status.RESOLVED), distinct=True),
    )
    
    # STABILIZE: Use manual python aggregation for complex cross-join metrics if ORM is inflating
    # Actually, let's keep it simple and fix the DISTINCT issue.
    # The inflation often happens when you have multiple M2M or reverse FKs.
    # Here we have assigned_issues (Reverse FK) and assigned_issues__domain_events (Reverse FK of Reverse FK).
    
    # RE-ANNOTATE CLEANLY
    officers_qs = OfficerProfile.objects.select_related("user", "department")
    if department:
        officers_qs = officers_qs.filter(department=department)
    if user and not user.is_superuser and user.role != "super_admin":
        admin_profile = getattr(user, 'admin_profile', None)
        if admin_profile and admin_profile.department:
            officers_qs = officers_qs.filter(department=admin_profile.department)

    # Use Subquery for each count to be 100% certain of accuracy
    officers_qs = officers_qs.annotate(
        real_assigned_count=Subquery(
            Issue.objects.filter(assigned_to=OuterRef('pk')).values('assigned_to').annotate(c=Count('id')).values('c')
        ),
        real_completed_count=Subquery(
            Issue.objects.filter(assigned_to=OuterRef('pk'), status=Issue.Status.RESOLVED).values('assigned_to').annotate(c=Count('id')).values('c')
        ),
        real_pending_count=Subquery(
            Issue.objects.filter(assigned_to=OuterRef('pk')).exclude(status=Issue.Status.RESOLVED).values('assigned_to').annotate(c=Count('id')).values('c')
        ),
        real_escalation_count=Subquery(
            IssueEvent.objects.filter(issue__assigned_to=OuterRef('pk'), event_type='escalated').values('issue__assigned_to').annotate(c=Count('issue_id', distinct=True)).values('c')
        )
    )

    # 5. Calculate Efficiency and handle nulls from Subquery
    officers_qs = officers_qs.annotate(
        assigned_count=Case(When(real_assigned_count__isnull=False, then=F('real_assigned_count')), default=Value(0)),
        completed_count=Case(When(real_completed_count__isnull=False, then=F('real_completed_count')), default=Value(0)),
        pending_count=Case(When(real_pending_count__isnull=False, then=F('real_pending_count')), default=Value(0)),
        escalation_count=Case(When(real_escalation_count__isnull=False, then=F('real_escalation_count')), default=Value(0)),
    )
    
    officers_qs = officers_qs.annotate(
        efficiency=ExpressionWrapper(
            Case(
                When(assigned_count__gt=0, then=F('completed_count') * 100.0 / F('assigned_count')),
                default=Value(0.0),
                output_field=FloatField()
            ),
            output_field=FloatField()
        )
    )

    # 6. Sort and Return Stats
    officers_qs = officers_qs.order_by('-efficiency', '-completed_count')

    # Prefetch unresolved assigned issues with AI context for is_overdue check
    from django.db.models import Prefetch
    unresolved_issues_prefetch = Prefetch(
        'assigned_issues',
        queryset=Issue.objects.exclude(status=Issue.Status.RESOLVED).select_related('ai_context'),
        to_attr='unresolved_issues'
    )
    officers_qs = officers_qs.prefetch_related(unresolved_issues_prefetch)

    stats = []
    for officer in officers_qs:
        # Calculate overdue percentage in python since it requires checking sla_days logic
        overdue_count = 0
        for issue in officer.unresolved_issues:
            if issue.is_overdue:
                overdue_count += 1
                
        overdue_pct = int((overdue_count / officer.pending_count * 100)) if officer.pending_count > 0 else 0
        
        # Calculate avg res time manually from prefetched resolved issues if needed, 
        # or just use a separate query for now for accuracy
        # For performance in a report, one extra query per officer is OK if we prefetch.
        # Let's see if we can get it from DB.
        
        # Calculate avg res time manually for accuracy
        avg_res = Issue.objects.filter(
            assigned_to=officer, 
            status=Issue.Status.RESOLVED, 
            resolved_at__isnull=False
        ).annotate(
            duration=ExpressionWrapper(F('resolved_at') - F('created_at'), output_field=DurationField())
        ).aggregate(avg=Avg('duration'))['avg']
        
        avg_hours = int(avg_res.total_seconds() / 3600) if avg_res else 0
        
        stats.append({
            "id": officer.id,
            "name": officer.user.full_name or officer.user.username,
            "email": officer.user.email,
            "is_active": officer.user.is_active,
            "department": officer.department.name,
            "assigned_count": officer.assigned_count,
            "completed_count": officer.completed_count,
            "pending_count": officer.pending_count,
            "overdue_count": overdue_count,
            "escalation_count": officer.escalation_count,
            "completion_rate": int(officer.efficiency),
            "efficiency": int(officer.efficiency),
            "avg_resolution_hours": avg_hours,
            "overdue_percentage": overdue_pct,
            "level": officer.get_level_display(),
            "district_name": officer.district,
            "taluka_name": officer.taluka or "N/A",
            "village_name": officer.village or officer.ward or officer.city or "N/A",
            "location": f"{officer.village}, {officer.taluka}" if officer.village else (officer.taluka or officer.district),
            "workload_capacity": officer.workload_capacity
        })

    return stats
def get_officer_form_context(user):
    # Only show departments/locations that this admin can manage
    if user.is_super_admin:
        depts = Department.objects.all()
        districts = Location.objects.filter(type=Location.Type.DISTRICT)
    else:
        depts = Department.objects.filter(id=user.admin_profile.department_id)
        # For simplicity, keeping all locations, but could be filtered by admin's region
        districts = Location.objects.filter(type=Location.Type.DISTRICT)
        
    return {
        "departments": depts,
        "districts": districts,
    }

def get_child_locations(parent_id, child_type):
    if not parent_id:
        return []
    return list(Location.objects.filter(parent_id=parent_id, type=child_type).values("id", "name"))

def create_officer_account(data):
    # This service should handle atomic user + officer creation
    from django.db import transaction
    from accounts.services import LocationService
    with transaction.atomic():
        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            full_name=data.get("full_name", ""),
            role=User.Role.OFFICER,
            is_approved=True,
            is_active=True
        )
        
        # Get location object if village_id provided, otherwise district
        loc_id = data.get("village_id") or data.get("taluka_id") or data.get("district_id")
        location = get_object_or_404(Location, id=loc_id)
        
        # STABILIZE: Resolve Hierarchy exactly once
        hierarchy = LocationService.resolve_hierarchy(location)
        
        officer = OfficerProfile.objects.create(
            user=user,
            department_id=data["department_id"],
            location=location,
            level=data["level"],
            village=hierarchy["village"],
            taluka=hierarchy["taluka"],
            district=hierarchy["district"],
            city=hierarchy["city"],
            zone=hierarchy["zone"],
            ward=hierarchy["ward"],
            
            # New Fields
            full_name=data.get("full_name"),
            phone=data.get("phone"),
            employee_id=data.get("employee_id"),
            designation=data.get("designation"),
            address=data.get("address")
        )
        return officer

def auto_assign_issue(issue):
    """
    Automatically assigns an issue using hardened unified logic.
    Delegates to issues.services for centralization.
    """
    from issues.services import auto_assign_issue as trigger_assignment
    return trigger_assignment(issue)

def mark_issue_resolved_for_user(issue, user, *, resolved_photo=None):
    from django.db import transaction
    with transaction.atomic():
        # Lock the issue for update
        issue = Issue.objects.select_for_update().get(pk=issue.pk)
        issue.status = Issue.Status.RESOLVED
        issue.resolved_at = timezone.now()
        issue.resolved_by = user
        if resolved_photo:
            issue.resolved_photo = resolved_photo
        issue.updated_by = user
        issue.save()

        # FEEDBACK LOOP: Trigger learning
        from issues.utils import update_intelligence_after_resolution
        update_intelligence_after_resolution(issue)

    return issue

def update_issue_from_payload(issue, data, user):
    for key, value in data.items():
        if value is not None and hasattr(issue, key):
            # Special handling for assigned_to to ensure location consistency
            if key == "assigned_to" and value:
                officer = OfficerProfile.objects.get(id=value)
                if issue.location and officer.location != issue.location:
                    # We skip assignment if mismatch (logic enforced in save() anyway)
                    continue
            setattr(issue, key, value)
    
    # Handle Location FK update if provided
    if "location" in data and data["location"]:
        issue.location_id = data["location"]

    issue.updated_by = user
    issue.save()
    return issue
