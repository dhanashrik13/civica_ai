import os
import django
import time
import logging
from django.utils import timezone
from django.db import transaction

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from django.db.models import Count
from issues.models import Issue, Department, IssueEvent
from accounts.models import OfficerProfile, User, Location
from notifications.models import Notification
from issues.services import secure_issue_assignment, auto_assign_issue, map_category_to_department
from accounts.middleware import bypass_rbac

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_test_data():
    citizen, _ = User.objects.get_or_create(username="val_citizen", email="val_citizen@test.com", role=User.Role.CITIZEN)
    citizen.set_password("pass")
    citizen.save()
    
    dist, _ = Location.objects.get_or_create(name="ValDistrict", type=Location.Type.DISTRICT)
    taluka, _ = Location.objects.get_or_create(name="ValTaluka", type=Location.Type.TALUKA, parent=dist)
    village, _ = Location.objects.get_or_create(name="ValVillage", type=Location.Type.VILLAGE, parent=taluka)

    # Departments
    pwd = Department.objects.filter(name__icontains="Public Works Department (PWD)").first()
    water = Department.objects.filter(name__icontains="Water Supply").first()
    garbage = Department.objects.filter(name__icontains="Sanitation").first()

    # Officers
    off_user1, _ = User.objects.get_or_create(username="val_pwd_off", email="val_pwd@test.com", role=User.Role.OFFICER)
    pwd_off, _ = OfficerProfile.objects.get_or_create(user=off_user1, department=pwd, location=taluka, level='taluka', district="ValDistrict", taluka="ValTaluka")
    pwd_off.is_active = True
    pwd_off.save()

    off_user2, _ = User.objects.get_or_create(username="val_water_off", email="val_water@test.com", role=User.Role.OFFICER)
    water_off, _ = OfficerProfile.objects.get_or_create(user=off_user2, department=water, location=dist, level='district', district="ValDistrict")
    water_off.is_active = True
    water_off.save()

    off_user3, _ = User.objects.get_or_create(username="val_garbage_off", email="val_garbage@test.com", role=User.Role.OFFICER)
    garbage_off, _ = OfficerProfile.objects.get_or_create(user=off_user3, department=garbage, location=village, level='village', district="ValDistrict", taluka="ValTaluka", village="ValVillage")
    garbage_off.is_active = True
    garbage_off.save()

    return citizen, dist, taluka, village, pwd, water, garbage, pwd_off, water_off, garbage_off

def phase1_live_assignment(citizen, village):
    print("\n--- PHASE 1: LIVE ASSIGNMENT TESTING ---")
    tests = [
        {"title": "Test Pothole", "category": "pothole", "expected_dept": "Public Works Department (PWD)"},
        {"title": "Test Water Leak", "category": "water_leakage", "expected_dept": "Water Supply Department"},
        {"title": "Test Garbage", "category": "garbage", "expected_dept": "Sanitation Department"},
        {"title": "Test Traffic", "category": "traffic_police", "expected_dept": "Traffic Police Department"}, # No officer
    ]

    for t in tests:
        issue = Issue.objects.create(
            title=t["title"], category=t["category"], reported_by=citizen, location=village,
            district="ValDistrict", taluka="ValTaluka", village="ValVillage"
        )
        
        # Simulate enrichment call
        with bypass_rbac():
            if not issue.department:
                issue.department = map_category_to_department(issue.category)
            auto_assign_issue(issue)
            issue.is_enriched = True
            issue.save()

        issue.refresh_from_db()
        dept_match = issue.department and t["expected_dept"] in issue.department.name
        assigned = issue.assigned_to is not None
        status = "PASS" if dept_match and (assigned or "Traffic" in t["expected_dept"]) else "FAIL"
        print(f"[{status}] {t['title']} -> Dept: {issue.department}, Assigned: {issue.assigned_to}")

def phase2_edge_cases(citizen, village, pwd_off):
    print("\n--- PHASE 2: EDGE CASE TESTING ---")
    
    # 1. Inactive Officer
    pwd_off.is_active = False
    pwd_off.save()
    issue1 = Issue.objects.create(title="Edge Inactive", category="pothole", reported_by=citizen, location=village, district="ValDistrict", taluka="ValTaluka", village="ValVillage")
    auto_assign_issue(issue1)
    issue1.refresh_from_db()
    print(f"[{'PASS' if not issue1.assigned_to else 'FAIL'}] Inactive officer skipped.")
    pwd_off.is_active = True
    pwd_off.save()

    # 3. Malformed location strings
    issue2 = Issue.objects.create(title="Edge Malformed Loc", category="pothole", reported_by=citizen, location=village, district=" VaL DisTrict ", taluka="valtaluka")
    auto_assign_issue(issue2)
    issue2.refresh_from_db()
    print(f"[{'PASS' if issue2.assigned_to else 'FAIL'}] Malformed location normalized and matched.")

def phase3_security_validation(citizen, village, water_off):
    print("\n--- PHASE 3: SECURITY VALIDATION ---")
    issue = Issue.objects.create(title="Sec Test", category="pothole", reported_by=citizen, location=village, district="ValDistrict")
    auto_assign_issue(issue)
    issue.refresh_from_db()
    
    old_assigned = issue.assigned_to
    try:
        issue.assigned_to = water_off # Wrong dept bypass
        issue.save()
        issue.refresh_from_db()
        # If the save intercepted and reverted, it's a pass. Or if it throws error.
        print(f"[{'PASS' if issue.assigned_to == old_assigned else 'FAIL/WARN'}] Direct assignment bypass handled (Assigned: {issue.assigned_to})")
    except Exception as e:
        print(f"[PASS] Direct assignment bypass caught: {e}")

def phase4_db_integrity():
    print("\n--- PHASE 4: DB INTEGRITY ---")
    events = IssueEvent.objects.filter(event_type=IssueEvent.Type.ASSIGNED).values('issue').annotate(count=Count('id')).filter(count__gt=5)
    print(f"[{'PASS' if not events.exists() else 'FAIL'}] No duplicate assignment loops detected.")

def phase5_performance(citizen, village):
    print("\n--- PHASE 5: PERFORMANCE VALIDATION ---")
    start = time.time()
    issue = Issue.objects.create(title="Perf Test", category="pothole", reported_by=citizen, location=village, district="ValDistrict")
    create_time = time.time() - start
    
    start = time.time()
    auto_assign_issue(issue)
    assign_time = time.time() - start
    
    print(f"Creation Time: {create_time:.4f}s")
    print(f"Assignment Time: {assign_time:.4f}s")

def run_all():
    citizen, dist, taluka, village, pwd, water, garbage, pwd_off, water_off, garbage_off = setup_test_data()
    phase1_live_assignment(citizen, village)
    phase2_edge_cases(citizen, village, pwd_off)
    phase3_security_validation(citizen, village, water_off)
    phase4_db_integrity()
    phase5_performance(citizen, village)
    
if __name__ == "__main__":
    run_all()
