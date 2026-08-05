import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from unittest.mock import patch
from django.db import transaction

# SILENCE REDIS/OUTBOX to focus on logic
patch('accounts.utils_async.dispatch_task_transactional').start()
patch('final_proj.celery.app.send_task').start()

from issues.models import Issue, IssueEvent
from accounts.models import User, Location, Department, OfficerProfile, PendingTask
from dashboards.models import DistrictDashboardProjection
from issues.projections import rebuild_district_projections, is_projection_stale
from dashboards.services import get_issue_counts
from issues.tasks import scan_and_escalate_issues

def simulate_partial_failure():
    print("--- PHASE: GOVERNANCE SAFETY UNDER PARTIAL FAILURE ---")
    
    # 0. CLEAN SLATE
    print("Step 0: Clearing existing data...")
    Issue.objects.all().delete()
    IssueEvent.objects.all().delete()
    DistrictDashboardProjection.objects.all().delete()
    PendingTask.objects.all().delete()
    OfficerProfile.objects.filter(user__username="test_officer").delete()

    # 1. SETUP
    dist, _ = Location.objects.get_or_create(name="Mumbai", type="district")
    dept, _ = Department.objects.get_or_create(name="Public Works")
    admin, _ = User.objects.get_or_create(username="test_admin", defaults={'email': 'a@t.com', 'role': User.Role.DEPT_ADMIN})
    if not hasattr(admin, 'admin_profile'):
        from accounts.models import AdminProfile
        AdminProfile.objects.create(user=admin, department=dept, district="Mumbai")

    citizen, _ = User.objects.get_or_create(username="test_citizen", defaults={'email': 'c@t.com', 'role': User.Role.CITIZEN})
    officer_user, _ = User.objects.get_or_create(username="test_officer", defaults={'email': 'o@t.com', 'role': User.Role.OFFICER})
    
    OfficerProfile.objects.create(user=officer_user, department=dept, location=dist, district="Mumbai", level="district", is_active=True)

    # 2. GENERATE ISSUES
    issue1 = Issue.objects.create(title="Normal Issue", category="Road", reported_by=citizen, location=dist, district="Mumbai", department=dept)
    
    # Issue 2 has human authority override
    issue2 = Issue.objects.create(title="Manual Override Issue", category="Road", reported_by=citizen, location=dist, district="Mumbai", department=dept, manual_override=True)
    
    # Make them overdue to trigger escalation
    Issue.objects.filter(id__in=[issue1.id, issue2.id]).update(created_at=django.utils.timezone.now() - django.utils.timezone.timedelta(days=10))

    # 3. TEST DEGRADED MODE READS (Stale Projection Fallback)
    print("\nStep 1: Testing Stale Data Safety Windows (Degraded Mode)...")
    # Manually create a stale projection
    proj = DistrictDashboardProjection.objects.create(
        district="Mumbai", department=dept, 
        pending_count=999, last_event_id=0
    )
    
    # Create an event to simulate lag (Projection last_event_id=0, but actual event > 10)
    current_seq = IssueEvent.objects.filter(issue=issue1).count()
    for i in range(15):
        IssueEvent.objects.create(issue=issue1, event_type=IssueEvent.Type.STATUS_CHANGED, sequence_number=current_seq + i + 1, payload={})
    
    # Test read
    counts = get_issue_counts(admin)
    if counts.get('source') == 'live_db':
        print(f"SUCCESS: System detected stale projection (event gap) and fell back to live_db. Pending: {counts['pending']}")
    else:
        print(f"FAILURE: System unsafely used stale projection! Source: {counts.get('source')}, Pending: {counts.get('pending')}")

    # 4. TEST DEGRADED MODE WRITES (Queue Backlog Prevents Automation)
    print("\nStep 2: Testing Automation Halt on Heavy Outbox Backlog...")
    # Simulate 1001 pending tasks
    tasks = [PendingTask(task_name="dummy") for _ in range(1001)]
    PendingTask.objects.bulk_create(tasks)
    
    escalated = scan_and_escalate_issues()
    if escalated is False:
        print("SUCCESS: Automation gracefully halted due to high backlog, preventing split-brain governance.")
    else:
        print(f"FAILURE: Automation blindly executed despite {PendingTask.objects.count()} backlogged tasks!")

    # 5. TEST AUTHORITY FENCES (Human Override Safety)
    print("\nStep 3: Testing Authority Fences (Human Override vs Automation)...")
    PendingTask.objects.all().delete() # Clear backlog
    
    escalated = scan_and_escalate_issues()
    issue1.refresh_from_db()
    issue2.refresh_from_db()
    
    from issues.utils import find_best_officer
    print(f"DEBUG: find_best_officer(issue1) -> {find_best_officer(issue1)}")
    print(f"DEBUG: Available Officers -> {list(OfficerProfile.objects.values('id', 'level', 'district', 'department_id', 'is_active'))}")
    print(f"DEBUG: Issue1 Dept -> {issue1.department_id}, District -> {issue1.district}")
    
    # Issue1 should be escalated, Issue2 should be skipped due to manual_override
    if issue1.assigned_to and not issue2.assigned_to:
        print(f"SUCCESS: Automation respected Authority Fence. Normal issue escalated. Manual override issue skipped.")
    else:
        print(f"FAILURE: Authority fence breached! Issue1 assigned: {bool(issue1.assigned_to)}, Issue2 assigned: {bool(issue2.assigned_to)}")

    # 6. TEST LIVE REPLAY ATOMIC SWAP
    print("\nStep 4: Testing Live Replay Atomic Swap Safety...")
    proj.pending_count = 500
    proj.save()
    
    print("Starting rebuild...")
    rebuild_district_projections()
    
    proj.refresh_from_db()
    if proj.pending_count == 500:
        print("FAILURE: Rebuild did not update projection!")
    else:
        print(f"SUCCESS: Live replay successfully atomically swapped the projection state. Pending is now: {proj.pending_count}")

if __name__ == "__main__":
    simulate_partial_failure()
