import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

import random
import time
from django.db import transaction
from unittest.mock import patch

# SILENCE REDIS/OUTBOX to focus on logic
patch('accounts.utils_async.dispatch_task_transactional').start()
patch('final_proj.celery.app.send_task').start()

from issues.models import Issue, IssueEvent
from accounts.models import User, Location, Department, OfficerProfile
from dashboards.models import DistrictDashboardProjection
from issues.projections import rebuild_district_projections, detect_projection_drift, process_issue_event

def simulate_governance_chaos():
    print("--- PHASE: EVENT CONSISTENCY & REPLAY SAFETY DRILL ---")
    
    # 0. CLEAN SLATE
    print("Step 0: Clearing existing data...")
    Issue.objects.all().delete()
    IssueEvent.objects.all().delete()
    DistrictDashboardProjection.objects.all().delete()

    # 1. SETUP
    dist, _ = Location.objects.get_or_create(name="Mumbai", type="district")
    dept = Department.objects.first()
    citizen, _ = User.objects.get_or_create(username="test_citizen", defaults={'email': 'c@t.com', 'role': User.Role.CITIZEN})
    officer_user, _ = User.objects.get_or_create(username="test_officer", defaults={'email': 'o@t.com', 'role': User.Role.OFFICER})
    if not hasattr(officer_user, 'officer'):
        OfficerProfile.objects.create(user=officer_user, department=dept, location=dist, district="Mumbai")

    # 2. GENERATE EVENTS
    print("Step 1: Generating Event Stream...")
    issue = Issue.objects.create(
        title="Event Consistency Test",
        category="Road",
        reported_by=citizen,
        location=dist,
        district="Mumbai",
        department=dept
    )
    
    # Simulate Assignment
    issue.assigned_to = officer_user.officer
    issue.status = Issue.Status.ASSIGNED
    issue.save()
    
    # Simulate Resolution
    issue.status = Issue.Status.RESOLVED
    issue.save()
    
    # 3. AUDIT EVENT STREAM
    print("Step 2: Auditing Event Stream Integrity...")
    events = IssueEvent.objects.filter(issue=issue).order_by('sequence_number')
    actual_types = [e.event_type for e in events]
    print(f"Actual Event Chain: {actual_types}")
    
    # 4. VERIFY PROJECTION
    print("Step 3: Verifying Projection Correctness...")
    for e in events:
        process_issue_event(e.id)
        
    drifts = detect_projection_drift()
    if not drifts:
        print("SUCCESS: Projections are consistent with source of truth.")
    else:
        print(f"FAILURE: Drift detected! {drifts}")

    # 5. REPLAY SAFETY DRILL
    print("Step 4: Replay Safety Drill (Deterministic Reconstruction)...")
    DistrictDashboardProjection.objects.filter(district="Mumbai", department=dept).update(pending_count=999)
    print("Projection corrupted manually. Starting rebuild...")
    
    start_time = time.time()
    rebuild_district_projections()
    duration = time.time() - start_time
    
    drifts_after = detect_projection_drift()
    if not drifts_after:
        print(f"SUCCESS: Rebuild complete and correct in {duration:.4f}s.")
    else:
        print(f"FAILURE: Rebuild produced drifted state! {drifts_after}")

    # 6. DUPLICATE DELIVERY TEST
    print("Step 5: Testing Idempotency (Duplicate Delivery)...")
    last_event = events.last()
    process_issue_event(last_event.id) 
    
    drifts_dup = detect_projection_drift()
    if not drifts_dup:
        print("SUCCESS: Handler is idempotent. Duplicate event ignored.")
    else:
        print(f"FAILURE: Duplicate event corrupted projection! {drifts_dup}")

if __name__ == "__main__":
    simulate_governance_chaos()
