from django.shortcuts import get_object_or_404
from accounts.models import Issue
from accounts.views import login_required
from .forms import  IssueStatusForm, IssueAssignmentForm

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ReportForm
from .models import Citizen

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.models import Citizen
from .models import Issue

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Issue
from accounts.models import Citizen

@login_required
def report_issue(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('accounts:login', role='Citizen')

    citizen = get_object_or_404(Citizen, id=user_id)

    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description')
            category = request.POST.get('category', 'General')
            location = request.POST.get('location', '')

            photo1 = request.FILES.get('photo1')
            photo2 = request.FILES.get('photo2')
            photo3 = request.FILES.get('photo3')

            Issue.objects.create(
                citizen=citizen,
                title=title,
                description=description,
                category=category,
                location=location,
                photo1=photo1,
                photo2=photo2,
                photo3=photo3,
                status='Pending'
            )

            messages.success(request, "Your issue has been submitted successfully!")
            return redirect('dashboards:citizen_dashboard')

        except Exception as e:
            print("Error while submitting issue:", e)
            messages.error(request, "Something went wrong while submitting your issue.")

    return render(request, 'issues/report_issue.html')

@login_required
def issue_list(request):
    try:
        # ✅ Get the citizen object using the session user_id
        citizen_id = request.session.get('user_id')
        citizen = Citizen.objects.get(id=citizen_id)

        # ✅ Fetch issues reported by this citizen
        issues = Issue.objects.filter(reported_by=citizen)

    except Citizen.DoesNotExist:
        messages.error(request, "Citizen profile not found.")
        return redirect('citizen_dashboard')

    return render(request, 'issues/issue_list.html', {'issues': issues})


@login_required
def issue_detail(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    return render(request, 'issues/issue_detail.html', {'issue': issue})


@login_required
def update_status(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.method == 'POST':
        form = IssueStatusForm(request.POST)
        if form.is_valid():
            issue.status = form.cleaned_data['status']
            issue.save()
            messages.success(request, "Status updated successfully!")
            return redirect('issues:issue_detail', pk=pk)
    else:
        form = IssueStatusForm(initial={'status': issue.status})
    return render(request, 'issues/update_status.html', {'form': form, 'issue': issue})


@login_required
def assign_issue(request, pk):
    issue = get_object_or_404(Issue, pk=pk)
    if request.method == 'POST':
        form = IssueAssignmentForm(request.POST)
        if form.is_valid():
            issue.assigned_officer = form.cleaned_data['officer']
            issue.save()
            messages.success(request, f"Issue assigned to {issue.assigned_officer.user.username}")
            return redirect('issues:issue_detail', pk=pk)
    else:
        form = IssueAssignmentForm()
    return render(request, 'issues/assign_issue.html', {'form': form, 'issue': issue})
