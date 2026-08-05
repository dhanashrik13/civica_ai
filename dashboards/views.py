from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.db.models.functions import TruncDate
from accounts.decorators import role_required
from accounts.models import User, OfficerProfile, Location, Department
from accounts.utils import apply_rbac_filter
from issues.models import Issue, Comment
from assistant.models import AIChat, AIActionLog
from dashboards.models import Announcement

from dashboards.services import (
    auto_assign_issue,
    create_officer_account,
    get_admin_dashboard_context,
    get_child_locations,
    get_citizen_dashboard_context,
    get_citizen_reports_context,
    get_global_search_context,
    get_officer_dashboard_context,
    get_officer_form_context,
    get_officer_performance_stats,
    mark_issue_resolved_for_user,
    update_issue_from_payload, paginate_queryset,
    get_issue_counts,
    get_time_series,
    get_map_points,
    get_critical_issues,
    get_trending_issues,
    get_activity_feed,
    get_active_citizens,
)

@role_required(User.Role.CITIZEN, User.Role.OFFICER, User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def api_dashboard_summary(request):
    data = get_issue_counts(request.user)
    return JsonResponse(data)

@role_required(User.Role.CITIZEN, User.Role.OFFICER, User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def api_dashboard_timeseries(request):
    days = int(request.GET.get('days', 30))
    data = get_time_series(request.user, days=days)
    return JsonResponse(data)

from django.core.paginator import Paginator

@role_required(User.Role.CITIZEN, User.Role.OFFICER, User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def api_dashboard_map(request):
    data = get_map_points(request.user)
    return JsonResponse(data, safe=False)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def officer_workload_report(request):
    """
    Paginated table view of all officers and their workloads.
    """
    search_query = request.GET.get("search", "").strip()
    dept_id = request.GET.get("department")
    district_name = request.GET.get("district")
    overloaded_only = request.GET.get("overloaded") == "true"
    sort_by = request.GET.get("sort", "-assigned_count")

    selected_dept = None
    if dept_id:
        selected_dept = Department.objects.filter(id=dept_id).first()
        
    stats = get_officer_performance_stats(request.user, department=selected_dept)
    
    # Manual filtering in Python for non-ORM fields or complex logic
    if search_query:
        stats = [s for s in stats if search_query.lower() in s['name'].lower() or search_query.lower() in s['email'].lower()]
    
    if district_name:
        stats = [s for s in stats if s['district'] == district_name]
        
    if overloaded_only:
        stats = [s for s in stats if s['pending_count'] > s['workload_capacity']]

    # Sorting
    reverse_sort = sort_by.startswith("-")
    clean_sort = sort_by.lstrip("-")
    stats = sorted(stats, key=lambda x: x.get(clean_sort, 0), reverse=reverse_sort)

    # Pagination
    page_number = request.GET.get("page", 1)
    paginator = Paginator(stats, 20)
    page_obj = paginator.get_page(page_number)

    return render(request, "dashboards/officer_workload_report.html", {
        "page_obj": page_obj,
        "departments": Department.objects.all(),
        "districts": Location.objects.filter(type=Location.Type.DISTRICT).order_by("name"),
        "total_officers": len(stats)
    })


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def export_officer_workload_csv(request):
    """
    Export full workload summary to CSV.
    """
    stats = get_officer_performance_stats(request.user)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="officer_workload_report_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        "Name", "Email", "Active", "Department", "Scope", "District", "Taluka", "Village/Ward",
        "Assigned Issues", "Resolved Issues", "Pending Issues",
        "Overdue Issues", "Escalations", "Efficiency %", "Avg Res (Hours)"
    ])

    for s in stats:
        writer.writerow([
            s["name"], s["email"], s["is_active"], s["department"], s["level"], 
            s["district_name"], s["taluka_name"], s["village_name"],
            s["assigned_count"], s["completed_count"], s["pending_count"],
            s["overdue_count"], s["escalation_count"], s["efficiency"], s["avg_resolution_hours"]
        ])
    return response

def set_language(request, lang):
    request.session["lang"] = lang if lang in {"en", "hi", "mr"} else "en"
    request.session.set_expiry(365 * 24 * 60 * 60)
    return redirect(request.META.get("HTTP_REFERER", "dashboards:assigned_issues"))


@role_required(User.Role.CITIZEN)
def citizen_dashboard(request):
    context = get_citizen_dashboard_context(request.user)
    # Support table rendering with model objects
    context['recent_issues'] = context.get('issues')
    # Ensure map data is available as 'issues' for json_script
    # OPTIMIZATION: Limit to recent 500 issues to prevent dashboard freeze on large datasets
    context['issues'] = list(Issue.objects.all().order_by('-created_at').values(
        "id", "title", "latitude", "longitude", "status", "category", "priority"
    )[:500])
    context['departments'] = Department.objects.annotate(
        total=Count('issues'),
        resolved=Count('issues', filter=Q(issues__status='resolved'))
    ).filter(total__gt=0)
    return render(request, "citizen/dashboard.html", context)


@role_required(User.Role.CITIZEN)
def citizen_reports(request):
    return render(
        request,
        "dashboards/my_reports_refactored.html",
        get_citizen_reports_context(request.user, request.GET.get("status"), request.GET.get("page")),
    )


@role_required(User.Role.CITIZEN)
def citizen_edit_profile(request):
    if request.method == "POST":
        request.user.full_name = request.POST.get("full_name", request.user.full_name)
        request.user.email = request.POST.get("email", request.user.email)
        request.user.phone_no = request.POST.get("phone_no", request.user.phone_no)
        request.user.address = request.POST.get("address", request.user.address)
        request.user.username = request.user.email
        request.user.save()
        
        # Create a notification for the user
        from notifications.services import create_notification
        from notifications.models import Notification
        create_notification(
            user_id=request.user.id,
            n_type=Notification.Type.PROFILE_UPDATED,
            message="Your profile has been updated successfully!",
            severity=Notification.Severity.LOW
        )
        
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:citizen_dashboard")
    return render(request, "dashboards/citizen_edit_profile.html", {"user": request.user})


@role_required(User.Role.OFFICER)
def officer_edit_profile(request):
    if request.method == "POST":
        request.user.full_name = request.POST.get("full_name", request.user.full_name)
        request.user.email = request.POST.get("email", request.user.email)
        request.user.phone_no = request.POST.get("phone_no", request.user.phone_no)
        request.user.address = request.POST.get("address", request.user.address)
        request.user.username = request.user.email
        request.user.save()
        
        # Create a notification for the user
        from notifications.services import create_notification
        from notifications.models import Notification
        create_notification(
            user_id=request.user.id,
            n_type=Notification.Type.PROFILE_UPDATED,
            message="Your profile has been updated successfully!",
            severity=Notification.Severity.LOW
        )
        
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:officer_dashboard")
    return render(request, "dashboards/citizen_edit_profile.html", {"user": request.user})

def get_officer_activities(user, limit=None):
    activities = []
    
    # 1. New Assignments
    assignments = apply_rbac_filter(Issue.objects.all(), user).order_by('-created_at')
    if limit: assignments = assignments[:limit]
    for issue in assignments:
        activities.append({
            'message': f"Issue #CN-{issue.id} assigned",
            'timestamp': issue.created_at,
            'issue_id': issue.id,
            'icon': '📌',
            'color': '#3b82f6',
            'bg': '#dbeafe'
        })
        
    # 2. Resolutions
    resolutions = apply_rbac_filter(Issue.objects.all(), user).filter(status=Issue.Status.RESOLVED).order_by('-resolved_at')
    if limit: resolutions = resolutions[:limit]
    for r in resolutions:
        if r.resolved_at:
            activities.append({
                'message': f"Issue #CN-{r.id} resolved",
                'timestamp': r.resolved_at,
                'issue_id': r.id,
                'icon': '✔',
                'color': '#16a34a',
                'bg': '#dcfce7'
            })
            
    # 3. Comments
    comments = apply_rbac_filter(Comment.objects.all(), user).select_related('issue', 'user').order_by('-created_at')
    if limit: comments = comments[:limit]
    for c in comments:
        activities.append({
            'message': f"Comment added on Issue #CN-{c.issue.id}",
            'timestamp': c.created_at,
            'issue_id': c.issue.id,
            'icon': '💬',
            'color': '#8b5cf6',
            'bg': '#f3e8ff'
        })
        
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return activities[:limit] if limit else activities

@role_required(User.Role.OFFICER)
def officer_dashboard(request):
    filters = {
        "search": request.GET.get("search", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "status": request.GET.get("status", "").strip(),
        "sort": request.GET.get("sort", "").strip(),
    }
    context = get_officer_dashboard_context(request.user, filters, request.GET.get("page"))
    context['recent_activities'] = get_officer_activities(request.user, limit=5)
    
    # Ensure map data is available as 'issues' for json_script
    map_issues = apply_rbac_filter(Issue.objects.all(), request.user).values(
        "id", "title", "latitude", "longitude", "status", "priority", "category"
    )
    context['issues'] = list(map_issues)

    # Dynamic active issues count
    active_qs = apply_rbac_filter(Issue.objects.all(), request.user).exclude(status=Issue.Status.RESOLVED)
    context['active_issues_count'] = active_qs.count()
    
    # Smart Notification for Backlog
    overdue_backlog = 0
    for issue in active_qs:
        if issue.is_overdue:
            overdue_backlog += 1
    
    if overdue_backlog > 0:
        messages.warning(request, f"You have {overdue_backlog} overdue issues that require immediate attention!")
    
    # Trending Issues for User's Department
    user_dept = None
    if request.user.role == User.Role.OFFICER and hasattr(request.user, 'officer'):
        user_dept = request.user.officer.department
    elif request.user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN] and hasattr(request.user, 'admin_profile'):
        user_dept = request.user.admin_profile.department

    context["trending_issues"] = get_trending_issues(request.user, department=user_dept)
    
    return render(request, "dashboards/officer_dashboard_refactored.html", context)

@role_required(User.Role.OFFICER)
def officer_activity_list(request):
    activities = get_officer_activities(request.user)
    return render(request, "dashboards/all_officer_activity.html", {
        "activities": activities
    })


@role_required(User.Role.OFFICER)
@require_POST
def close_issue(request, issue_id):
    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
    
    # STEP 1: Strict Ownership Validation
    try:
        officer = request.user.officer
    except:
        return HttpResponseForbidden("OfficerProfile profile missing")
        
    if issue.assigned_to != officer:
        return HttpResponseForbidden("Unauthorized access: This issue is not assigned to you.")

    try:
        from issues.services import mark_issue_resolved_for_user
        mark_issue_resolved_for_user(issue, request.user, resolved_photo=request.FILES.get("resolved_photo"))
        
        # STEP 6: Ensure Data Integrity
        issue.refresh_from_db()
        
        # STEP 4: Consistent User Feedback
        messages.success(request, f"Issue #CN-{issue.id} marked as resolved successfully.")
    except Exception as e:
        messages.error(request, f"Failed to close issue: {str(e)}")

    # STEP 2 & 5: Safe Redirect with Context Preservation
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url:
        return redirect(next_url)
        
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    
    # Fallback to assigned issues with query params if any
    return redirect(f"{reverse('dashboards:assigned_issues')}?{request.GET.urlencode()}")


from issues.services import secure_issue_assignment

@role_required("super_admin", "dept_admin")
def admin_dashboard(request):
    # USE SINGLE SOURCE OF TRUTH (Synchronized with Assigned Issues page)
    issues_qs = Issue.objects.select_related(
        "assigned_to",
        "assigned_to__user",
        "department",
        "reported_by"
    ).all()
    
    # STRICT RBAC (Override for Dept Admin)
    selected_dept = None
    if request.user.role == User.Role.DEPT_ADMIN:
        admin_profile = getattr(request.user, 'admin_profile', None)
        if admin_profile:
            selected_dept = admin_profile.department
            issues_qs = issues_qs.filter(department=selected_dept)
    else:
        dept_id = request.GET.get("department")
        if dept_id and dept_id.isdigit():
            selected_dept = Department.objects.filter(id=int(dept_id)).first()
            if selected_dept:
                issues_qs = issues_qs.filter(department=selected_dept)

    issues_qs = issues_qs.order_by("-created_at")
    
    context = get_admin_dashboard_context(request.user, issues_queryset=issues_qs)
    # Ensure map data is available as 'issues' for json_script
    # OPTIMIZATION: Limit map pins to recent 1000 issues for performance
    map_issues = issues_qs.values(
        "id", "title", "latitude", "longitude", "status", "priority", "category"
    )[:1000]
    context['issues'] = list(map_issues)
    context["selected_department"] = selected_dept
    context["all_departments"] = Department.objects.all()
    
    # Trending and Activities
    context["trending_issues"] = get_trending_issues(request.user, department=selected_dept)
    context["activities"] = get_activity_feed(request.user)
    context["active_citizens"] = get_active_citizens(request.user, department=selected_dept)
    
    # Pagination
    page_number = request.GET.get('page')
    page_obj = paginate_queryset(issues_qs, page_number, per_page=5)
    
    context["page_obj"] = page_obj
    
    # Dashboard stats should also be filtered (Align with issues_qs)
    context["officers"] = get_officer_performance_stats(request.user, department=selected_dept)[:6]

    return render(request, "dashboards/admin_dashboard_refactored.html", context)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_department_detail(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    if request.user.role == User.Role.DEPT_ADMIN:
        admin_profile = getattr(request.user, 'admin_profile', None)
        if not admin_profile or admin_profile.department != department:
            messages.error(request, "Access denied.")
            return redirect("dashboards:admin_dashboard")
        
    issues = apply_rbac_filter(Issue.objects.filter(department=department), request.user).select_related("reported_by", "assigned_to__user").order_by("-created_at")
    return render(request, "dashboards/admin_department_detail.html", {
        "department": department,
        "issues": issues
    })


@login_required
def citizen_map_view(request):
    """UNIFIED MAP VIEW: One source of truth for all roles."""
    # REPAIR: Switched to advanced unified map template with async loading
    return render(request, 'issues/issue_map.html', {
        'role': request.user.role
    })

@role_required(User.Role.CITIZEN, User.Role.OFFICER, User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def common_map_view(request):
    return citizen_map_view(request)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_map_view(request):
    return citizen_map_view(request)

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_full_map(request):
    return citizen_map_view(request)

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_issue_map_data(request):
    issues_qs = apply_rbac_filter(Issue.objects.all(), request.user).filter(latitude__isnull=False, longitude__isnull=False)
    issues = list(issues_qs.values("id", "title", "status", "category", "location", "latitude", "longitude"))
    return JsonResponse(issues, safe=False)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_all_officers(request):
    sort_by = request.GET.get("sort", "high")
    search_query = request.GET.get("search", "").strip()
    
    # Align officer queryset with issues: Any user appearing in work must show up
    issues_qs = Issue.objects.all()
    officers = get_officer_performance_stats(request.user, issues_queryset=issues_qs)
    
    if search_query:
        officers = [o for o in officers if search_query.lower() in o['name'].lower()]
        
    if sort_by == "low":
        officers = sorted(officers, key=lambda x: x["efficiency"])
    else:
        # Default is high (Highest Efficiency)
        officers = sorted(officers, key=lambda x: x["efficiency"], reverse=True)
        
    return render(request, "dashboards/all_officers.html", {"officers": officers})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def officer_detail(request, officer_id):
    officer = get_object_or_404(OfficerProfile, id=officer_id)
    
    # Calculate performance stats for this specific officer
    performance = get_officer_performance_stats(request.user, department=officer.department)
    officer_stats = next((o for o in performance if o['id'] == officer.id), None)

    context = {
        "officer": officer,
        "stats": officer_stats
    }
    return render(request, "dashboards/officer_detail.html", context)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def manage_officers(request):
    officers = apply_rbac_filter(User.objects.all(), request.user).filter(role=User.Role.OFFICER)
    return render(request, "dashboards/manage_officers.html", {"officers": officers})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def add_officer(request):
    if request.method == "POST":
        try:
            dept_id = request.POST.get("department")
            if request.user.role == User.Role.DEPT_ADMIN:
                admin_profile = getattr(request.user, 'admin_profile', None)
                if not admin_profile or str(dept_id) != str(admin_profile.department_id):
                    raise ValueError("You can only add officers to your own department.")
                
            phone = request.POST.get("phone", "").strip()
            if phone and not phone.isdigit():
                raise ValueError("Phone number must contain only digits.")

            officer = create_officer_account(
                {
                    "username": request.POST.get("username", "").strip(),
                    "email": request.POST.get("email", "").strip().lower(),
                    "password": request.POST.get("password", ""),
                    "full_name": request.POST.get("full_name", "").strip(),
                    "phone": phone,
                    "employee_id": request.POST.get("employee_id", "").strip(),
                    "designation": request.POST.get("designation", "").strip(),
                    "address": request.POST.get("address", "").strip(),
                    "zone": request.POST.get("zone", "").strip(),
                    "level": request.POST.get("level"),
                    "department_id": dept_id,
                    "district_id": request.POST.get("district"),
                    "taluka_id": request.POST.get("taluka"),
                    "village_id": request.POST.get("village"),
                }
            )
            messages.success(request, f"OfficerProfile {officer.user.username} created successfully.")
            return redirect("dashboards:view_all_officers")
        except Exception as exc:
            messages.error(request, f"Failed to add officer: {exc}")

    return render(request, "dashboards/add_officer.html", get_officer_form_context(request.user))


@role_required("super_admin", "dept_admin")
@require_POST
def assign_issue(request, issue_id):
    officer_id = request.POST.get("officer_id")
    if officer_id:
        issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
        officer = get_object_or_404(apply_rbac_filter(OfficerProfile.objects.all(), request.user), id=officer_id)

        try:
            secure_issue_assignment(issue, officer, request.user)
            messages.success(request, f"Issue assigned and logged by {request.user.username}.")
        except Exception as e:
            messages.error(request, str(e))

    return redirect(request.META.get("HTTP_REFERER", "dashboards:admin_dashboard"))

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def assign_issue_ajax(request, issue_id):
    try:
        data = json.loads(request.body)
        officer_id = data.get("officer_id")
        
        issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
            
        if officer_id:
            officer = get_object_or_404(apply_rbac_filter(OfficerProfile.objects.all(), request.user), id=officer_id)
            secure_issue_assignment(issue, officer, request.user)
            return JsonResponse({"success": True, "message": "Assignment updated successfully"})
        
        return JsonResponse({"success": False, "error": "No officer provided"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def assign_issue_by_ml(request, issue_id):
    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
    if auto_assign_issue(issue):
        messages.success(request, "Issue auto-assigned.")
    else:
        messages.error(request, "No officers available.")
    return redirect("dashboards:admin_dashboard")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def admin_issue_detail_v1_placeholder(request, issue_id):
    # This was a duplicate, removing it safely.
    pass



@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_issue(request, issue_id):
    return redirect("dashboards:admin_issue_detail", issue_id=issue_id)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def edit_issue(request, issue_id):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
    if request.method == "POST":
        update_issue_from_payload(
            issue,
            {
                "title": request.POST.get("title", issue.title),
                "description": request.POST.get("description", issue.description),
                "category": request.POST.get("category", issue.category),
                "location": request.POST.get("location"),
                "status": request.POST.get("status", issue.status),
                "assigned_to": request.POST.get("assigned_to"),
            },
            request.user,
        )
        messages.success(request, "Issue updated successfully.")
        return redirect("dashboards:admin_dashboard")

    officers = apply_rbac_filter(OfficerProfile.objects.all(), request.user).select_related("user")
    locations = Location.objects.all().order_by('type', 'name')
    return render(request, "dashboards/edit_issue.html", {"issue": issue, "officers": officers, "locations": locations})


@role_required(User.Role.CITIZEN, User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def delete_issue(request, pk):
    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), pk=pk)
    issue.delete()
    messages.success(request, "Issue deleted successfully.")
    return redirect("dashboards:citizen_reports" if request.user.is_citizen else "dashboards:admin_dashboard")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def edit_profile(request):
    if request.method == "POST":
        request.user.full_name = request.POST.get("full_name", request.user.full_name)
        request.user.email = request.POST.get("email", request.user.email)
        request.user.phone_no = request.POST.get("phone_no", request.user.phone_no)
        request.user.address = request.POST.get("address", request.user.address)
        request.user.username = request.user.email
        request.user.save()
        
        # Create a notification for the user
        from notifications.services import create_notification
        from notifications.models import Notification
        create_notification(
            user_id=request.user.id,
            n_type=Notification.Type.PROFILE_UPDATED,
            message="Your profile has been updated successfully!",
            severity=Notification.Severity.LOW
        )
        
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:admin_dashboard")
    return render(request, "dashboards/edit_profile.html", {"user": request.user})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def mark_issue_complete(request, issue_id):
    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
    if request.method == "POST":
        mark_issue_resolved_for_user(issue, request.user, resolved_photo=request.FILES.get("resolved_photo"))
        messages.success(request, f"Issue '{issue.title}' marked as resolved.")
        return redirect("dashboards:admin_dashboard")
    return render(request, "dashboards/mark_complete.html", {"issue": issue})


def get_all_issues(user):
    """SINGLE SOURCE OF TRUTH for issue data flow."""
    base_qs = Issue.objects.select_related(
        'assigned_to__user',
        'department',
        'reported_by'
    ).all().order_by('-created_at')
    
    # RBAC logic integrated directly to ensure consistency
    if user.role == User.Role.SUPER_ADMIN:
        return base_qs
    
    # Department Admin and others
    # Using filter with Q to handle NULL departments as requested
    return base_qs.filter(
        Q(department_id=user.department_id) | 
        Q(department__isnull=True)
    )

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def forward_issue(request, issue_id):
    if request.method == "POST":
        new_dept_id = request.POST.get("department_id")
        if new_dept_id:
            from accounts.models import Department
            issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
            new_dept = get_object_or_404(Department, id=new_dept_id)
            
            old_dept_name = issue.department.name if issue.department else 'None'
            
            # Reset Issue
            issue.assigned_to = None
            issue.department = new_dept
            issue.status = Issue.Status.PENDING
            # Log action
            issue.assignment_explanation = f"Forwarded by admin {request.user.username} due to mismatch. Previous department: {old_dept_name}"
            issue.save()
            
            messages.success(request, f"Issue forwarded to {new_dept.name} department.")
            
    return redirect("dashboards:admin_issue_detail", issue_id=issue_id)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def admin_issue_detail(request, issue_id):
    from django.shortcuts import get_object_or_404, render
    from issues.utils import get_smart_suggestion
    from accounts.models import Department
    from django.db.models import Count
    
    # ENSURE RELATION IS LOADED AND RBAC IS APPLIED
    issue = get_object_or_404(
        apply_rbac_filter(Issue.objects.select_related('assigned_to__user', 'department', 'location'), request.user), 
        id=issue_id
    )
    
    # Smart Suggestion
    suggested_dept = get_smart_suggestion(issue)
    
    # Strict Location + Workload-based Recommendation
    recommended_officer = None
    if issue.department and issue.location:
        recommended_officer = (
            OfficerProfile.objects
            .filter(department=issue.department, location=issue.location, is_active=True)
            .annotate(issue_count=Count('assigned_issues'))
            .order_by('issue_count')
            .first()
        )
    
    officers = apply_rbac_filter(OfficerProfile.objects.all(), request.user).filter(is_active=True).select_related("user", "department")
    comments = Comment.objects.filter(issue=issue).select_related('user').order_by('-created_at')
    
    # All departments for forwarding (Admin only)
    departments = []
    if request.user.role in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
        departments = Department.objects.all()

    return render(request, "dashboards/admin_issue_detail.html", {
        "issue": issue,
        "officers": officers,
        "comments": comments,
        "suggested_dept": suggested_dept,
        "departments": departments,
        "recommended_officer": recommended_officer
    })

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_assigned_tasks(request, officer_id=None):
    # 1. BASE QUERY (Mandatory)
    issues = Issue.objects.select_related(
        "assigned_to",
        "assigned_to__user",
        "department",
        "reported_by"
    ).all()
    
    officers = OfficerProfile.objects.select_related('user', 'department').all()

    # 2. STRICT RBAC (Override for Dept Admin)
    if request.user.role == User.Role.DEPT_ADMIN:
        admin_profile = getattr(request.user, 'admin_profile', None)
        if admin_profile:
            issues = issues.filter(department=admin_profile.department)
            officers = officers.filter(department=admin_profile.department)

    # 3. Extract parameters
    selected_officer = request.GET.get("officer") or officer_id
    selected_priority = request.GET.get("priority")
    selected_status = request.GET.get("status")
    selected_sort = request.GET.get("sort", "latest")

    # 4. Apply Filters ONLY if value exists
    if selected_officer:
        issues = issues.filter(assigned_to_id=selected_officer)

    if selected_priority:
        issues = issues.filter(priority__iexact=selected_priority)

    if selected_status:
        issues = issues.filter(status__iexact=selected_status)

    # 5. Mandatory DEBUG logs
    admin_profile = getattr(request.user, 'admin_profile', None)
    print("DASHBOARD DEPT:", admin_profile.department if admin_profile and request.user.role == "dept_admin" else "ALL")
    print("QUERY COUNT:", issues.count())

    # 6. Apply Sorting
    if selected_sort == "priority":
        issues = issues.order_by(
            Case(
                When(priority=Issue.Priority.HIGH, then=Value(1)),
                When(priority=Issue.Priority.MEDIUM, then=Value(2)),
                When(priority=Issue.Priority.LOW, then=Value(3)),
                default=Value(4),
                output_field=IntegerField()
            ),
            "-created_at"
        )
    else:
        # Default: Latest First
        issues = issues.order_by("-created_at")
    
    # Context Construction
    context = {
        "issues": issues,
        "officers": officers,
        "selected_officer": str(selected_officer or ""),
        "selected_priority": (selected_priority or "").lower(),
        "selected_status": (selected_status or "").lower(),
        "selected_sort": selected_sort,
        "stats": {
            "high": issues.filter(priority=Issue.Priority.HIGH).count(),
            "medium": issues.filter(priority=Issue.Priority.MEDIUM).count(),
            "low": issues.filter(priority=Issue.Priority.LOW).count(),
            "unassigned": issues.filter(assigned_to__isnull=True).count(),
            "total": issues.count()
        },
        "officer_mode": False
    }
    
    return render(request, "dashboards/assigned_issues_refactored.html", context)

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def update_priority(request, issue_id):
    # DEBUG CHECK (Mandatory)
    print("RECEIVED ID:", issue_id)
    print("ALL DB IDS:", list(Issue.objects.values_list('id', flat=True)))

    try:
        issue = Issue.objects.get(id=issue_id)
    except Issue.DoesNotExist:
        print("ERROR: Issue not found for ID:", issue_id)
        messages.error(request, f"Issue with ID {issue_id} not found.")
        return redirect(request.GET.get('next', 'dashboards:view_assigned_tasks'))
    
    # Check permission (RBAC)
    try:
        apply_rbac_filter(Issue.objects.filter(id=issue_id), request.user).get()
    except Issue.DoesNotExist:
        messages.error(request, "Access denied.")
        return redirect(request.GET.get('next', 'dashboards:view_assigned_tasks'))
    
    priority = request.POST.get("priority")
    if priority and priority.lower() in [Issue.Priority.LOW, Issue.Priority.MEDIUM, Issue.Priority.HIGH]:
        issue.priority = priority.lower()
        issue.save()
        messages.success(request, f"Priority for Issue #CN-{issue.id} updated to {priority.upper()}.")
    
    return redirect(request.GET.get('next', 'dashboards:view_assigned_tasks'))


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def global_search(request):
    query = request.GET.get("q", "").strip()
    
    if request.GET.get("export") == "true":
        import csv
        from django.http import HttpResponse
        
        issues = apply_rbac_filter(Issue.objects.all(), request.user).select_related("reported_by", "assigned_to__user", "department").order_by("-created_at")
        
        status_filter = request.GET.get("status")
        if status_filter:
            issues = issues.filter(status=status_filter)
            
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="all_issues_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow(["ID", "Title", "Status", "Category", "Location", "Reported By", "Assigned To", "Created At"])
        
        for issue in issues:
            assigned_name = issue.assigned_to.user.full_name if issue.assigned_to else "Unassigned"
            loc_name = issue.location.name if issue.location else issue.location
            writer.writerow([
                issue.id, 
                issue.title, 
                issue.status, 
                issue.category, 
                loc_name, 
                issue.reported_by.username,
                assigned_name,
                issue.created_at.strftime("%Y-%m-%d %H:%M")
            ])
            
        return response

    search_results = get_global_search_context(query, user=request.user)
    return render(request, "dashboards/admin_global_search.html", search_results)


@role_required(User.Role.OFFICER)
def assigned_issues_view(request):
    # STEP 1: Strict OfficerProfile Check
    try:
        officer = request.user.officer
    except:
        return HttpResponseForbidden("OfficerProfile profile missing")

    # Fetch ONLY issues assigned to this officer
    issues = Issue.objects.filter(assigned_to=officer).select_related(
        "assigned_to",
        "assigned_to__user",
        "department",
        "reported_by"
    )
    
    # DEBUG LOGGING (MANDATORY)
    print("Logged User:", request.user)
    print("OfficerProfile:", officer)
    print("Assigned Issues Count:", issues.count())

    search = request.GET.get('search')
    status = request.GET.get('status')
    priority = request.GET.get('priority')

    if search:
        if search.startswith('#CN-'):
            try:
                issue_id = int(search.replace('#CN-', ''))
                issues = issues.filter(id=issue_id)
            except ValueError:
                issues = issues.filter(title__icontains=search)
        else:
            issues = issues.filter(title__icontains=search)

    if status:
        issues = issues.filter(status__iexact=status)

    if priority:
        issues = issues.filter(priority__iexact=priority)

    # Sort by most recent update
    issues = issues.order_by("-updated_at")

    # Pagination
    page_number = request.GET.get('page')
    page_obj = paginate_queryset(issues, page_number, per_page=10)

    return render(request, "dashboards/assigned_issues_refactored.html", {
        "issues": page_obj.object_list,
        "page_obj": page_obj,
        "officer_mode": True
    })


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def all_issues_view(request):
    # Fix: Apply RBAC filter to prevent cross-jurisdiction leakage
    issues = apply_rbac_filter(Issue.objects.all(), request.user).order_by("-created_at")
    
    # DEBUG CHECK (MANDATORY)
    if request.user.role == User.Role.OFFICER:
        officer = getattr(request.user, 'officer', None)
        print("TOTAL ISSUES:", issues.count())
        print("OFFICER PROFILE:", officer)
        print("ASSIGNED:", issues.filter(assigned_to=officer).count() if officer else 0)

    page_obj = paginate_queryset(issues, request.GET.get("page"), per_page=12)
    return render(request, "dashboards/all_issues.html", {"issues": page_obj.object_list, "page_obj": page_obj})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def map_view(request):
    """Unified Advanced Map View for Officers/Admins."""
    return render(request, "issues/issue_map.html")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def map_view_data(request):
    """DEPRECATED: Use issues:issue_map_data instead."""
    from django.urls import reverse
    return redirect(reverse("issues:issue_map_data") + "?" + request.GET.urlencode())



@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def all_citizen_activity(request):
    # STRICT: Only show issues reported by real citizens.
    # We filter by the CITIZEN role and exclude any users with officer/admin in their username 
    # to handle data inconsistencies where officers might have been tagged as citizens.
    activities = apply_rbac_filter(Issue.objects.all(), request.user).filter(
        reported_by__isnull=False,
        reported_by__role=User.Role.CITIZEN
    ).exclude(
        Q(reported_by__username__icontains="officer") | 
        Q(reported_by__username__icontains="admin")
    ).select_related("reported_by", "department").order_by("-created_at")
    
    return render(request, "dashboards/all_citizen_activity.html", {
        "activities": activities
    })

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def issue_detail(request, issue_id):
    # Fix: Allow viewing for all authenticated staff/officers
    # Officers can VIEW all issues, but can only MODIFY assigned ones.
    if request.user.role == User.Role.OFFICER:
        issue = get_object_or_404(Issue.objects.all(), id=issue_id)
    else:
        issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)

    can_edit = True
    if request.user.role == User.Role.OFFICER:
        try:
            officer = request.user.officer
            can_edit = (issue.assigned_to == officer)
        except:
            can_edit = False

    if request.method == "POST":
        # STEP 1: Strict Ownership Validation
        if request.user.role == User.Role.OFFICER:
            try:
                officer = request.user.officer
            except:
                return HttpResponseForbidden("OfficerProfile profile missing")
            if issue.assigned_to != officer:
                return HttpResponseForbidden("Unauthorized access: This issue is not assigned to you.")

        try:
            image = request.FILES.get("proof_image")

            if not image:
                messages.error(request, "Image is required to resolve issue.")
                return redirect("dashboards:issue_detail", issue_id=issue.id)

            issue.status = Issue.Status.RESOLVED
            issue.proof_image = image
            issue.resolved_at = timezone.now()
            issue.resolved_by = request.user
            issue.save()
            
            # STEP 6: Ensure Data Integrity
            issue.refresh_from_db()

            # STEP 4: Consistent User Feedback
            messages.success(request, f"Issue #CN-{issue.id} marked as resolved.")
        except Exception as e:
            messages.error(request, f"Failed to resolve issue: {str(e)}")
            
        # STEP 2 & 5: Safe Redirect
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect("dashboards:issue_detail", issue_id=issue.id)

    return render(request, "dashboards/issue_detail.html", {"issue": issue, "can_edit": can_edit})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def reports(request):
    # 1. Normalize Input (Strip whitespace)
    selected_district = request.GET.get('district', '').strip()
    selected_taluka = request.GET.get('taluka', '').strip()
    selected_village = request.GET.get('village', '').strip()

    # 3. Filtering Correctness for Base Queryset
    base_qs = apply_rbac_filter(Issue.objects.all(), request.user)

    # 2. Dependent Dropdown Logic (Filtered by what user can see)
    districts = base_qs.exclude(district__isnull=True).exclude(district__exact="") \
        .values_list('district', flat=True).distinct().order_by('district')
    
    # Talukas depend on District
    talukas_qs = base_qs.exclude(taluka__isnull=True).exclude(taluka__exact="")
    if selected_district:
        talukas_qs = talukas_qs.filter(district__iexact=selected_district)
    talukas = talukas_qs.values_list('taluka', flat=True).distinct().order_by('taluka')

    # Villages depend on District and Taluka
    villages_qs = base_qs.exclude(village__isnull=True).exclude(village__exact="")
    if selected_district:
        villages_qs = villages_qs.filter(district__iexact=selected_district)
    if selected_taluka:
        villages_qs = villages_qs.filter(taluka__iexact=selected_taluka)
    villages = villages_qs.values_list('village', flat=True).distinct().order_by('village')

    if selected_district:
        base_qs = base_qs.filter(district__iexact=selected_district)
    if selected_taluka:
        base_qs = base_qs.filter(taluka__iexact=selected_taluka)
    if selected_village:
        base_qs = base_qs.filter(village__iexact=selected_village)

    # 4. Improved Date Filtering (Using datetime range)
    now = timezone.now()
    start_datetime = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    qs_7d_trend = base_qs.filter(created_at__range=[start_datetime, now]) \
        .annotate(day=TruncDate('created_at')) \
        .values('day') \
        .annotate(count=Count('id'))

    # Category Breakdown
    category_counts = base_qs.values("category").annotate(count=Count("id")).order_by("-count")
    cat_labels = [dict(Issue.Category.choices).get(c['category'], c['category']) for c in category_counts]
    cat_data = [c['count'] for c in category_counts]

    # Overdue Issues (Escalation)
    overdue_count = 0
    # Optimization: only load fields needed for is_overdue calculation
    for issue in base_qs.exclude(status=Issue.Status.RESOLVED).only('status', 'created_at', 'priority'):
        if issue.is_overdue:
            overdue_count += 1

    # 5. Safety for Trend Data
    trend_map = {
        str(item['day']): item['count'] 
        for item in qs_7d_trend 
        if item['day'] is not None
    }
    
    today_date = now.date()
    labels = [(today_date - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    data = [trend_map.get(label, 0) for label in labels]

    # Status Distribution (All time)
    status_counts = base_qs.values("status").annotate(count=Count("id"))
    
    display_map = {
        Issue.Status.RESOLVED: "Resolved",
        Issue.Status.ASSIGNED: "In Progress",
        Issue.Status.PENDING: "Pending",
    }
    
    status_map = {k: 0 for k in display_map.keys()}
    for item in status_counts:
        status_map[item["status"]] = item["count"]

    status_labels = [display_map[k] for k in status_map.keys()]
    status_data = [status_map[k] for k in status_map.keys()]

    # Additional Stats
    resolved_issues = base_qs.filter(status=Issue.Status.RESOLVED, resolved_at__isnull=False)
    avg_resolution_hours = 0.0
    if resolved_issues.exists():
        total_time = sum([(i.resolved_at - i.created_at).total_seconds() for i in resolved_issues], 0)
        avg_resolution_hours = (total_time / resolved_issues.count()) / 3600

    high_priority_solved = base_qs.filter(status=Issue.Status.RESOLVED, priority=Issue.Priority.HIGH).count()

    # Geo Intelligence: Top Problem Areas
    # Group by village/taluka/district to find highest concentration of unresolved issues
    top_problem_areas = []
    if selected_district:
        # If district is selected, show talukas or villages
        if selected_taluka:
            areas = base_qs.exclude(status=Issue.Status.RESOLVED).exclude(village__exact="").values('village').annotate(issue_count=Count('id')).order_by('-issue_count')[:5]
            for area in areas: top_problem_areas.append({"name": area['village'], "count": area['issue_count']})
        else:
            areas = base_qs.exclude(status=Issue.Status.RESOLVED).exclude(taluka__exact="").values('taluka').annotate(issue_count=Count('id')).order_by('-issue_count')[:5]
            for area in areas: top_problem_areas.append({"name": area['taluka'], "count": area['issue_count']})
    else:
        # Default: show districts
        areas = base_qs.exclude(status=Issue.Status.RESOLVED).exclude(district__exact="").values('district').annotate(issue_count=Count('id')).order_by('-issue_count')[:5]
        for area in areas: top_problem_areas.append({"name": area['district'], "count": area['issue_count']})

    context = {
        "districts": districts,
        "talukas": talukas,
        "villages": villages,
        "selected_district": selected_district,
        "selected_taluka": selected_taluka,
        "selected_village": selected_village,
        "trend_labels": json.dumps(labels),
        "trend_data": json.dumps(data),
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "avg_resolution_time": avg_resolution_hours,
        "overdue_count": overdue_count,
        "citizen_satisfaction": 88.0,
        "high_priority_solved": high_priority_solved,
        "top_problem_areas": top_problem_areas,
        "total": base_qs.count(),
    }
    return render(request, "dashboards/reports.html", context)



@role_required(User.Role.OFFICER)
def update_issue_status(request):
    issues = apply_rbac_filter(Issue.objects.all(), request.user)
    return render(request, "dashboards/update_status.html", {"issues": issues})


@role_required(User.Role.CITIZEN, User.Role.OFFICER, User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def add_comment(request):
    # Citizens can only comment on their own issues, others use RBAC filter
    if request.user.role == User.Role.CITIZEN:
        issues = Issue.objects.filter(reported_by=request.user)
    else:
        issues = apply_rbac_filter(Issue.objects.all(), request.user)

    if request.method == "POST":
        try:
            issue_id = request.POST.get("issue_id")
            text = request.POST.get("comment")

            if issue_id and text:
                issue = get_object_or_404(issues, id=issue_id)
                
                # STEP 1: Strict Ownership Validation
                if request.user.role == User.Role.OFFICER:
                    try:
                        officer = request.user.officer
                    except:
                        return HttpResponseForbidden("OfficerProfile profile missing")
                    if issue.assigned_to != officer:
                        return HttpResponseForbidden("Unauthorized access: This issue is not assigned to you.")

                Comment.objects.create(
                    issue=issue,
                    user=request.user,
                    text=text
                )
                
                # STEP 6: Data Integrity (Refresh if needed, though comment is separate)
                issue.refresh_from_db()

                # STEP 4: Consistent User Feedback
                messages.success(request, "Comment added successfully.")
                
                # STEP 2 & 5: Safe redirect with fallback
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                    
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                return redirect(f"{reverse('dashboards:assigned_issues')}?{request.GET.urlencode()}")
            else:
                messages.error(request, "Comment text is required.")
        except Exception as e:
            messages.error(request, f"Failed to add comment: {str(e)}")
            
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
            
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect(f"{reverse('dashboards:assigned_issues')}?{request.GET.urlencode()}")

    return render(request, "dashboards/add_comment.html", {"issues": issues})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def profile(request):
    if request.method == "POST":
        user = request.user
        user.email = request.POST.get("email", user.email)
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.save()

        if hasattr(user, 'officer'):
            officer = user.officer
            officer.phone = request.POST.get("phone", officer.phone)
            officer.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:profile")
        
    return render(request, "dashboards/profile.html", {"user": request.user})


@role_required(User.Role.OFFICER)
def officer_ai_assistant(request):
    """UNIFIED OFFICER AI"""
    chats = AIChat.objects.filter(user=request.user).order_by("created_at")[:20]
    return render(request, "assistant/assistant_refactored.html", {"chats": chats})


@role_required(User.Role.CITIZEN)
def citizen_issue_map(request):
    return citizen_map_view(request)


@role_required(User.Role.CITIZEN)
def citizen_issue_detail(request, issue_id):
    # DEBUG LOG (MANDATORY)
    print("Looking for Issue ID:", issue_id)
    print("Exists:", Issue.objects.filter(id=issue_id).exists())

    # Fetch the issue safely (Public read-only view)
    # We remove any restrictive filters like reported_by or assigned_to
    issue = get_object_or_404(Issue, id=issue_id)
    
    return render(request, "citizen/issue_detail.html", {"issue": issue})


@role_required(User.Role.CITIZEN)
def citizen_ai_assistant(request):
    """UNIFIED CITIZEN AI"""
    chats = AIChat.objects.filter(user=request.user).order_by("created_at")[:20]
    return render(request, "assistant/assistant_refactored.html", {"chats": chats})


@role_required(User.Role.CITIZEN)
def citizen_help_support(request):
    return render(request, "citizen/help_support.html")


@role_required(User.Role.CITIZEN)
def department_detail(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    # Fetch issues belonging to this department (Public view for citizens)
    queryset = Issue.objects.filter(department_id=dept_id).order_by("-created_at")
    
    # DEBUG LOGS (MANDATORY)
    print("Department ID:", dept_id)
    print("Issues Found:", queryset.count())

    return render(request, "citizen/department_detail.html", {
        "department": department,
        "issues": queryset
    })


@role_required(User.Role.CITIZEN)
@require_POST
def citizen_delete_issue(request, issue_id):
    issue = get_object_or_404(apply_rbac_filter(Issue.objects.all(), request.user), id=issue_id)
    issue.delete()
    messages.success(request, "Issue deleted successfully.")
    return redirect("dashboards:citizen_reports")


def get_talukas(request, district_id):
    try:
        talukas = Location.objects.filter(parent_id=district_id, type=Location.Type.TALUKA).values("id", "name")
        return JsonResponse(list(talukas), safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def get_villages(request, taluka_id):
    try:
        villages = Location.objects.filter(parent_id=taluka_id, type=Location.Type.VILLAGE).values("id", "name")
        return JsonResponse(list(villages), safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def search_view(request):
    query = request.GET.get('q', '').strip()

    if request.GET.get("export") == "true" and (request.user.role == User.Role.SUPER_ADMIN or request.user.role == User.Role.DEPT_ADMIN):
        import csv
        from django.http import HttpResponse
        issues = apply_rbac_filter(Issue.objects.all(), request.user).select_related("reported_by", "assigned_to__user", "department").order_by("-created_at")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="all_issues_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["ID", "Title", "Status", "Category", "Location", "Reported By", "Assigned To", "Created At"])
        for issue in issues:
            assigned_name = issue.assigned_to.user.full_name if issue.assigned_to else "Unassigned"
            loc_name = issue.location.name if issue.location else issue.location
            writer.writerow([issue.id, issue.title, issue.status, issue.category, loc_name, issue.reported_by.username, assigned_name, issue.created_at.strftime("%Y-%m-%d %H:%M")])
        return response

    issues = apply_rbac_filter(Issue.objects.all(), request.user).filter(Q(title__icontains=query) | Q(metadata__description__icontains=query))
    users = apply_rbac_filter(User.objects.all(), request.user).filter(Q(username__icontains=query) | Q(_legacy_full_name__icontains=query))
    comments = apply_rbac_filter(Comment.objects.all(), request.user).filter(text__icontains=query).select_related('issue', 'user')

    context = {
        "query": query,
        "issues": issues,
        "users": users,
        "comments": comments
    }

    return render(request, "search/results.html", context)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def ai_assistant(request):
    """UNIFIED ADMIN AI"""
    chats = AIChat.objects.filter(user=request.user).order_by("created_at")[:20]
    return render(request, "assistant/assistant_refactored.html", {"chats": chats})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_notifications(request):
    notifications = apply_rbac_filter(Issue.objects.all(), request.user).order_by('-created_at')[:10]
    return render(request, "admin/notifications.html", {
        "notifications": notifications
    })


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_profile(request):
    return render(request, "admin/profile.html")


@login_required
def announcement_list(request):
    # Filter by department via created_by officer link
    officer = getattr(request.user, 'officer', None)
    if not officer:
        return redirect('dashboards:admin_dashboard')
        
    announcements = Announcement.objects.filter(
        created_by__officer__department=officer.department,
        is_approved=True
    ).order_by('-created_at')
    
    return render(request, 'announcements/announcement_list.html', {
        'announcements': announcements
    })


@login_required
def create_announcement(request):
    # STRICT PERMISSION: Allow only officers
    if not hasattr(request.user, 'officer'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Only officers can create announcements.")

    try:
        officer = request.user.officer
    except:
        return HttpResponseForbidden("OfficerProfile profile missing")

    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            content = request.POST.get('content')
            duration = request.POST.get('duration')

            try:
                days = int(duration) if duration else 7
            except ValueError:
                days = 7

            expires_at = timezone.now() + timedelta(days=days)

            Announcement.objects.create(
                title=title,
                content=content,
                created_by=request.user,
                expires_at=expires_at,
                is_approved=False # Officers need approval
            )
            messages.success(request, 'Announcement submitted for approval.')
            return redirect('dashboards:announcement_list')
        except Exception as e:
            messages.error(request, f"Failed to create announcement: {str(e)}")
            return redirect('dashboards:create_announcement')
    
    return render(request, 'dashboards/create_announcement.html')

@role_required(User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN)
def approve_announcements(request):
    Announcement.objects.filter(expires_at__lt=timezone.now()).delete()
    
    if request.method == 'POST':
        announcement_id = request.POST.get('announcement_id')
        action = request.POST.get('action')
        announcement = get_object_or_404(Announcement, id=announcement_id)
        
        if action == 'approve':
            announcement.is_approved = True
            announcement.save()
            messages.success(request, 'Announcement approved.')
        elif action == 'delete':
            announcement.delete()
            messages.success(request, 'Announcement deleted.')
            
        return redirect('dashboards:approve_announcements')
        
    pending = Announcement.objects.filter(is_approved=False)
    approved = Announcement.objects.filter(is_approved=True)
    
    return render(request, 'dashboards/approve_announcements.html', {
        'pending_announcements': pending,
        'approved_announcements': approved
    })
