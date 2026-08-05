from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import Location, OfficerProfile
from issues.models import Issue

from .services import (
    assign_issue_to_officer,
    auto_assign_issue,
    create_officer_account,
    get_admin_dashboard_context,
    get_admin_issue_map_context,
    get_admin_map_points,
    get_all_issues_context,
    get_assigned_tasks_context,
    get_child_locations,
    get_citizen_dashboard_context,
    get_citizen_reports_context,
    get_global_search_context,
    get_manage_officers_context,
    get_officer_assignment_context,
    get_officer_dashboard_context,
    get_officer_directory,
    get_officer_form_context,
    get_officer_map_points,
    get_report_summary_context,
    mark_issue_resolved_for_user,
    paginate_queryset,
    update_dashboard_profile,
    update_issue_from_payload,
)

User = get_user_model()


def set_language(request, lang):
    request.session["lang"] = lang if lang in {"en", "hi", "mr"} else "en"
    request.session.set_expiry(365 * 24 * 60 * 60)
    return redirect(request.META.get("HTTP_REFERER", "/"))


@role_required(User.Role.CITIZEN)
def citizen_dashboard(request):
    return render(
        request,
        "dashboards/citizen_dashboard_refactored.html",
        get_citizen_dashboard_context(request.user),
    )


@role_required(User.Role.CITIZEN)
def citizen_reports(request):
    reports = get_citizen_reports_context(request.user, request.GET.get("status"))
    page_obj = paginate_queryset(reports, request.GET.get("page"), per_page=10)
    return render(
        request,
        "dashboards/my_reports_refactored.html",
        {
            "reports": page_obj.object_list,
            "page_obj": page_obj,
            "selected_status": request.GET.get("status", ""),
        },
    )


@role_required(User.Role.CITIZEN)
def citizen_edit_profile(request):
    if request.method == "POST":
        update_dashboard_profile(request.user, request.POST)
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:citizen_dashboard")
    return render(request, "dashboards/citizen_edit_profile.html", {"user": request.user})


@role_required(User.Role.OFFICER)
def officer_dashboard(request):
    filters = {
        "search": request.GET.get("search", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "status": request.GET.get("status", "").strip(),
        "sort": request.GET.get("sort", "").strip(),
    }
    return render(
        request,
        "dashboards/officer_dashboard_refactored.html",
        get_officer_dashboard_context(request.user, filters, request.GET.get("page")),
    )


@role_required(User.Role.OFFICER)
def close_issue(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id, assigned_to=request.user.officer)
    if request.method == "POST":
        mark_issue_resolved_for_user(issue, request.user, resolved_photo=request.FILES.get("resolved_photo"))
        messages.success(request, "Issue closed successfully.")
    return redirect("dashboards:assigned_issues")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_dashboard(request):
    return render(request, "dashboards/admin_dashboard_refactored.html", get_admin_dashboard_context())


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_issue_map(request):
    return render(
        request,
        "dashboards/admin_map.html",
        {
            **get_admin_issue_map_context(),
            "map_data_url": "dashboards:admin_issue_map_data",
        },
    )


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def admin_issue_map_data(request):
    return JsonResponse({"issues": get_admin_map_points(request)})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_officers(request):
    return render(request, "dashboards/view_officer.html", {"officers": get_officer_directory()})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def manage_officers(request):
    return render(request, "dashboards/manage_officers.html", {"officers": get_manage_officers_context()})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def add_officer(request):
    if request.method == "POST":
        try:
            officer = create_officer_account(
                {
                    "email": request.POST.get("email", "").strip().lower(),
                    "password": request.POST.get("password", ""),
                    "full_name": request.POST.get("full_name", "").strip(),
                    "level": request.POST.get("level"),
                    "department_id": request.POST.get("department"),
                    "district_id": request.POST.get("district"),
                    "taluka_id": request.POST.get("taluka"),
                    "village_id": request.POST.get("village"),
                }
            )
            messages.success(request, f"OfficerProfile {officer.user.username} created successfully.")
            return redirect("dashboards:view_officer")
        except Exception as exc:
            messages.error(request, f"Failed to add officer: {exc}")

    return render(request, "dashboards/add_officer.html", get_officer_form_context())


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def assign_issue(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)
    if request.method == "POST":
        officer = get_object_or_404(OfficerProfile, user_id=request.POST.get("officer_id"), user__role=User.Role.OFFICER)
        assign_issue_to_officer(issue, officer)
        messages.success(request, "Issue assigned successfully.")
    return redirect("dashboards:admin_dashboard")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def assign_issue_by_ml(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)
    if auto_assign_issue(issue):
        messages.success(request, "Issue auto-assigned.")
    else:
        messages.error(request, "No officers available.")
    return redirect("dashboards:admin_dashboard")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_issue(request, issue_id):
    return redirect("dashboards:admin_issue_detail", issue_id=issue_id)


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def edit_issue(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)
    if request.method == "POST":
        update_issue_from_payload(
            issue,
            {
                "title": request.POST.get("title", issue.title),
                "description": request.POST.get("description", issue.description),
                "category": request.POST.get("category", issue.category),
                "location": request.POST.get("location", issue.location),
                "status": request.POST.get("status", issue.status),
                "assigned_to": request.POST.get("assigned_to"),
            },
            request.user,
        )
        messages.success(request, "Issue updated successfully.")
        return redirect("dashboards:admin_dashboard")

    officers = OfficerProfile.objects.filter(user__role=User.Role.OFFICER).select_related("user")
    return render(request, "dashboards/edit_issue.html", {"issue": issue, "officers": officers})


@role_required(User.Role.CITIZEN, User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def delete_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.user.is_citizen and issue.reported_by != request.user:
        messages.error(request, "You do not have permission to delete this issue.")
        return redirect("dashboards:citizen_reports")
    issue.delete()
    messages.success(request, "Issue deleted successfully.")
    return redirect("dashboards:citizen_reports" if request.user.is_citizen else "dashboards:admin_dashboard")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def edit_profile(request):
    if request.method == "POST":
        update_dashboard_profile(request.user, request.POST)
        messages.success(request, "Profile updated successfully.")
        return redirect("dashboards:admin_dashboard")
    return render(request, "dashboards/edit_profile.html", {"user": request.user})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def mark_issue_complete(request, issue_id):
    issue = get_object_or_404(Issue, id=issue_id)
    if request.method == "POST":
        mark_issue_resolved_for_user(issue, request.user, resolved_photo=request.FILES.get("resolved_photo"))
        messages.success(request, f"Issue '{issue.title}' marked as resolved.")
        return redirect("dashboards:admin_dashboard")
    return render(request, "dashboards/mark_complete.html", {"issue": issue})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def view_assigned_tasks(request, officer_id=None):
    return render(
        request,
        "dashboards/assigned_issues_refactored.html",
        get_assigned_tasks_context(
            officer_id=officer_id,
            selected_officer=request.GET.get("officer"),
            page_number=request.GET.get("page"),
        ),
    )


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def global_search(request):
    return render(
        request,
        "dashboards/admin_global_search.html",
        get_global_search_context(request.GET.get("q", "").strip()),
    )


@role_required(User.Role.OFFICER)
def assigned_issues_view(request):
    return render(
        request,
        "dashboards/assigned_issues_refactored.html",
        {
            **get_officer_assignment_context(
                request.user,
                request.GET.get("priority", "").strip(),
                request.GET.get("page"),
            ),
            "officer_mode": True,
        },
    )


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def all_issues(request):
    filters = {
        "search": request.GET.get("search", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "status": request.GET.get("status", "").strip(),
    }
    return render(request, "dashboards/all_issues.html", get_all_issues_context(filters, request.GET.get("page")))


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def map_view(request):
    return render(
        request,
        "dashboards/map_view.html",
        {"map_data_url": "dashboards:map_view_data"},
    )


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def map_view_data(request):
    officer = request.user.officer if request.user.is_officer else None
    return JsonResponse({"issues": get_officer_map_points(request, officer=officer)})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER)
def reports(request):
    return render(request, "dashboards/reports.html", get_report_summary_context())


@role_required(User.Role.OFFICER)
def profile(request):
    if request.method == "POST":
        update_dashboard_profile(request.user, request.POST)
        messages.success(request, "OfficerProfile profile updated successfully.")
        return redirect("dashboards:profile")
    return render(request, "dashboards/profile.html", {"user": request.user})


def get_talukas(request):
    return JsonResponse(get_child_locations(request.GET.get("district_id"), Location.Type.TALUKA), safe=False)


def get_villages(request):
    return JsonResponse(get_child_locations(request.GET.get("taluka_id"), Location.Type.VILLAGE), safe=False)
