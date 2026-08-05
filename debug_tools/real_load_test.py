import os
import django
import time
import concurrent.futures
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from django.test import Client
from accounts.models import User, Location, Department, OfficerProfile

def setup_test_data():
    print("Setting up test data...")
    from accounts.middleware import bypass_rbac
    
    with bypass_rbac():
        # Ensure departments and locations exist
        dept, _ = Department.objects.get_or_create(name="Public Works Department (PWD)", level="district")
        dist, _ = Location.objects.get_or_create(name="Test District", type="district")
        
        citizen, _ = User.objects.get_or_create(username="load_citizen", email="load_citizen@test.com")
        if not citizen.password:
            citizen.set_password("password123")
            citizen.role = User.Role.CITIZEN
            citizen.save(skip_clean=True)

        officer_user, _ = User.objects.get_or_create(username="load_officer", email="load_officer@test.com")
        if not officer_user.password:
            officer_user.set_password("password123")
            officer_user.role = User.Role.OFFICER
            officer_user.save(skip_clean=True)
            
        OfficerProfile.objects.get_or_create(
            user=officer_user, department=dept, location=dist, level="district",
            defaults={"active_assigned_count": 0, "fatigue_level": 0}
        )

        admin_user, _ = User.objects.get_or_create(username="load_admin", email="load_admin@test.com")
        if not admin_user.password:
            admin_user.set_password("password123")
            admin_user.role = User.Role.SUPER_ADMIN
            admin_user.save(skip_clean=True)

    return citizen, officer_user, admin_user, dept, dist

def simulate_citizen_report(citizen_creds, dept_id, dist_id):
    client = Client()
    client.login(username=citizen_creds[0], password=citizen_creds[1])
    
    # Real endpoint execution (assuming an endpoint exists for this, if not, we use the model directly to test concurrency)
    # Since we need to test real endpoint execution, let's look at the available views.
    # But for concurrency lock contention on Issue and OfficerProfile, hitting the DB concurrently is the goal.
    pass

def worker_reassign(admin_creds, issue_id, officer_id):
    client = Client()
    client.login(username=admin_creds[0], password=admin_creds[1])
    # Hit the assign endpoint
    start = time.time()
    response = client.post(f'/dashboard/admin/issue/{issue_id}/assign/', {'officer_id': officer_id})
    return time.time() - start, response.status_code

def test_concurrent_reassignment(admin_user, officer_user, dist):
    print("--- DRILL: Concurrent Reassignment & Lock Contention ---")
    from issues.models import Issue
    # Create an issue
    issue = Issue.objects.create(
        title="Concurrency Test Issue",
        description="Testing locks",
        category="Road",
        reported_by=admin_user,
        location=dist,
        status="pending"
    )
    
    # Run 20 concurrent reassignments of the same issue to the same officer
    # This will heavily test select_for_update on the officer metrics
    admin_creds = ("load_admin", "password123")
    
    times = []
    statuses = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_reassign, admin_creds, issue.id, officer_user.officer.id) for _ in range(20)]
        for f in concurrent.futures.as_completed(futures):
            try:
                t, status = f.result()
                times.append(t)
                statuses.append(status)
            except Exception as e:
                print(f"Request failed: {e}")
                
    officer_user.officer.refresh_from_db()
    print(f"Results: {len(times)} requests completed.")
    print(f"Average time: {sum(times)/len(times):.4f}s")
    print(f"Final OfficerProfile Active Count: {officer_user.officer.active_assigned_count}")
    print(f"Final OfficerProfile Fatigue: {officer_user.officer.fatigue_level}")
    
    # Check if active count is 1 (since it's the same issue assigned 20 times)
    if officer_user.officer.active_assigned_count == 1:
        print("CONCURRENCY SAFE: No metric drift observed.")
    else:
        print("CONCURRENCY FAILED: Metric drift detected!")

if __name__ == "__main__":
    citizen, officer, admin, dept, dist = setup_test_data()
    test_concurrent_reassignment(admin, officer, dist)
