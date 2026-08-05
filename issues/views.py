import json
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import OfficerProfile

from .forms import IssueAssignmentForm, ReportForm
from .models import Issue
from .utils import get_priority
from .services import (
    secure_issue_assignment as assign_issue_service,
    get_issue_map_points,
    get_public_issue_list_context,
    get_location_payload,
    paginate_queryset,
    resolve_village_selection,
    update_issue_status,
    map_category_to_department
)

User = get_user_model()


import requests
from django.views.decorators.http import require_GET

@login_required
@require_GET
def resolve_gis_location(request):
    """
    ENTERPRISE GIS RESOLUTION ENGINE.
    Resolves real-time GPS coordinates to internal Location hierarchy.
    """
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    
    if not lat or not lng:
        return JsonResponse({"error": "Missing coordinates"}, status=400)

    try:
        # 1. Reverse Geocode via OSM Nominatim
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
        headers = {"User-Agent": "CivicPulse/1.0", "Accept-Language": "en"}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        if "address" not in data:
            return JsonResponse({"error": "No address found"}, status=404)

        addr = data["address"]
        
        # 2. Extract components
        district_name = addr.get("county") or addr.get("state_district") or ""
        city_name = addr.get("city") or addr.get("town") or addr.get("municipality") or ""
        area_name = addr.get("suburb") or addr.get("neighbourhood") or addr.get("village") or addr.get("hamlet") or ""
        
        clean_dist = district_name.replace(" District", "").strip()
        
        # 3. Dynamic Internal Matching
        from accounts.models import Location
        results = {"status": "success", "resolved_address": data.get("display_name")}
        
        dist_obj = Location.objects.filter(name__iexact=clean_dist, type=Location.Type.DISTRICT).first()
        if dist_obj:
            results["district_id"] = dist_obj.id
            results["district_name"] = dist_obj.name
            
            # Try to match city/taluka
            child_obj = Location.objects.filter(
                parent=dist_obj, 
                name__icontains=city_name
            ).first() if city_name else None
            
            if child_obj:
                results["taluka_id" if child_obj.type == 'taluka' else "city_id"] = child_obj.id
                results["child_name"] = child_obj.name
                
                # Try to match village/ward
                leaf_obj = Location.objects.filter(
                    parent=child_obj, 
                    name__icontains=area_name
                ).first() if area_name else None
                
                if leaf_obj:
                    results["village_id" if leaf_obj.type == 'village' else "ward_id"] = leaf_obj.id
                    results["leaf_name"] = leaf_obj.name

        return JsonResponse(results)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@role_required("citizen")
def report_issue(request):
    from accounts.models import Location
    
    locations_qs, location_payload = None, []

    if request.method == "POST":
        # Determine which ID to resolve based on scope
        scope = request.POST.get("governance_scope")
        location_id = request.POST.get("village_id") or request.POST.get("ward_id") or \
                      request.POST.get("taluka_id") or request.POST.get("city_id") or \
                      request.POST.get("district_id")

        loc_obj = None
        if location_id:
            try:
                loc_obj = Location.objects.get(id=location_id)
            except (Location.DoesNotExist, ValueError):
                pass

        # Create form early to check validity before potentially slow location payload fetch
        form = ReportForm(request.POST, request.FILES)
        
        if not loc_obj:
            form.add_error("governance_scope", "Please select a valid location matching the selected scope.")
        else:
            # Trace hierarchy for legacy fields and display
            district, taluka, village, ward, city = "", "", "", "", ""
            
            curr = loc_obj
            while curr:
                if curr.type == 'village': village = curr.name
                elif curr.type == 'taluka': taluka = curr.name
                elif curr.type == 'district': district = curr.name
                elif curr.type == 'ward': ward = curr.name
                elif curr.type == 'city': city = curr.name
                curr = curr.parent
            
            # Inject traced data into form cleaned_data
            post_data = request.POST.copy()
            post_data["district"] = district
            post_data["taluka"] = taluka
            post_data["village"] = village
            post_data["ward"] = ward
            post_data["city"] = city
            post_data["location"] = " > ".join(
                part for part in [district, city or taluka, ward or village] if part
            )
            form = ReportForm(post_data, request.FILES)

        if form.is_valid():
            # FIXED: Securely build issue report with validated data
            issue = form.save(commit=False)
            issue.reported_by = request.user
            
            # EXPLICIT DEPARTMENT ASSIGNMENT
            issue.department = map_category_to_department(issue.category)
            
            # EXPLICIT LOCATION ASSIGNMENT
            issue.location = loc_obj
            
            # Legacy fields
            issue.district = district
            issue.taluka = taluka
            issue.village = village
            issue.ward = ward
            issue.city = city
            
            # STRICT RULE: No officer assignment at creation time
            issue.assigned_to = None
            issue.status = Issue.Status.PENDING
            
            issue.save()
            
            messages.success(request, "Issue reported successfully!")
            return redirect("dashboards:citizen_dashboard")
        else:
            # POST Failed validation: Need location payload to re-render dropdowns
            _, location_payload = get_location_payload()
            messages.error(request, "Please correct the errors below and resubmit the form.")
    else:
        # GET request: Initial form load
        form = ReportForm()
        _, location_payload = get_location_payload()

    return render(request, "issues/report_issue_refactored.html", {
        "form": form, 
        "locations": location_payload
    })


@login_required
def issue_detail_redirect(request, pk):
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
        return redirect("accounts:redirect_dashboard")

    return redirect("dashboards:admin_issue_detail", issue_id=pk)


@login_required
def issue_detail(request, pk):
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
        return redirect("accounts:redirect_dashboard")

    return redirect("dashboards:admin_issue_detail", issue_id=pk)


@login_required
def map_issue_detail(request, issue_id):
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
        return redirect("accounts:redirect_dashboard")

    return redirect("dashboards:admin_issue_detail", issue_id=issue_id)


from django.views.decorators.http import require_POST

@role_required(User.Role.OFFICER, User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def update_status(request, pk):
    # Production Hardening: Explicit Role & Ownership Check
    if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN, User.Role.OFFICER]:
        messages.error(request, "Access denied.")
        return redirect("accounts:redirect_dashboard")

    issue = get_object_or_404(Issue, pk=pk)
    
    # Ownership check for officers
    if request.user.role == User.Role.OFFICER:
        try:
            officer = request.user.officer
        except:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("OfficerProfile profile missing")
            
        if issue.assigned_to != officer:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Unauthorized access: This issue is not assigned to you.")

    try:
        update_issue_status(
            issue,
            request.POST.get("status"),
            request.user,
            resolved_photo=request.FILES.get("resolved_photo"),
        )
        issue.refresh_from_db()
        messages.success(request, "Status updated successfully!")
    except Exception as exc:
        messages.error(request, f"Update failed: {str(exc)}")

    # Redirect back to the detail page
    return redirect("dashboards:admin_issue_detail", issue_id=pk)


@login_required
def issue_map(request):
    issues = get_issue_map_points(request.user)
    # Serialize to JSON to avoid template rendering issues with types
    issues_json = json.dumps(issues)
    
    return render(request, "issues/issue_map.html", {
        "issues_json": issues_json,
        "map_data_url": "issues:issue_map_data"
    })


@login_required
def issue_map_data(request):
    # Support for Officer "My Assigned Issues" toggle
    assigned_to_id = None
    
    # ENFORCE OFFICER ISOLATION (Phase 5 Hardening)
    # If the user is an officer, they MUST only see their assigned issues on their specific map.
    if request.user.role == "officer" and hasattr(request.user, 'officer'):
        assigned_to_id = request.user.officer.id
    elif request.GET.get("assigned_to_me") == "true" and hasattr(request.user, 'officer'):
        assigned_to_id = request.user.officer.id

    return JsonResponse(
        {
            "issues": get_issue_map_points(
                request.user,
                bounds={
                    "north": float(request.GET["north"]),
                    "south": float(request.GET["south"]),
                    "east": float(request.GET["east"]),
                    "west": float(request.GET["west"]),
                }
                if all(key in request.GET for key in ("north", "south", "east", "west"))
                else None,
                status=request.GET.get("status") or None,
                category=request.GET.get("category") or None,
                assigned_to_id=assigned_to_id,
                priority=request.GET.get("priority") or None,
            )
        }
    )


def issue_list(request):
    department_id = request.GET.get("department")
    page_number = request.GET.get("page")
    context = get_public_issue_list_context(page_number, department_id=department_id, user=request.user)
    return render(request, "issues/issue_list_refactored.html", context)
