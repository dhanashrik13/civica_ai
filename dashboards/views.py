from django.shortcuts import render, get_object_or_404
from django.contrib import messages

from django.shortcuts import render, redirect

from accounts.models import Citizen, Officer
from accounts.views import login_required
# Create your views here.



# -----------------------------
# DASHBOARDS
# -----------------------------

from django.contrib.auth.decorators import login_required

from issues.models import Issue
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import Citizen
from issues.models import Issue

@login_required
def citizen_dashboard(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('accounts:login', role='Citizen')

    citizen = Citizen.objects.get(id=user_id)

    # Base queryset
    all_issues = Issue.objects.filter(citizen=citizen)

    # Counts for dashboard cards
    total_issues = all_issues.count()
    pending_issues = all_issues.filter(status='Pending').count()
    resolved_issues = all_issues.filter(status='Resolved').count()

    # Filter by dropdown (GET request)
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'all':
        issues = all_issues.order_by('-created_at')
    else:
        issues = all_issues.filter(status=status_filter).order_by('-created_at')

    context = {
        'citizen': citizen,
        'issues': issues,
        'status_filter': status_filter,
        'total_issues': total_issues,
        'pending_issues': pending_issues,
        'resolved_issues': resolved_issues,
    }

    return render(request, 'dashboards/citizen_dashboard.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.models import Citizen
from django.contrib.auth.decorators import login_required

@login_required
def citizen_edit_profile(request):
    try:
        user_id = request.session.get('user_id')
        citizen = get_object_or_404(Citizen, id=user_id)

        if request.method == 'POST':
            citizen.full_name = request.POST.get('full_name')
            citizen.email = request.POST.get('email')
            citizen.phone = request.POST.get('phone')
            citizen.address = request.POST.get('address')
            citizen.save()
            messages.success(request, "✅ Profile updated successfully!")
            return redirect('dashboards:citizen_dashboard')

        return render(request, 'dashboards/citizen_edit_profile.html', {'citizen': citizen})

    except Exception as e:
        print("Profile update error:", e)
        messages.error(request, "⚠️ Something went wrong while updating your profile.")
        return redirect('dashboards:citizen_dashboard')





@login_required
def officer_dashboard(request):
    user_id = request.session.get("user_id")
    if not user_id:
        messages.error(request, "Please log in first.")
        return redirect("choose_role", action="login")
    user = get_object_or_404(Officer, id=user_id)
    return render(request, "dashboards/officer_dashboard.html", {"user": user})

@login_required
def admin_dashboard(request):
    pending_issues = Issue.objects.filter(status="Pending")
    in_progress_issues = Issue.objects.filter(status="In Progress")
    resolved_issues = Issue.objects.filter(status="Resolved")

    context = {
        "pending_issues": pending_issues,
        "in_progress_issues": in_progress_issues,
        "resolved_issues": resolved_issues,
    }
    return render(request, "dashboards/admin_dashboard.html", context)
