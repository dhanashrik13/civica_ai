
import os
import django
import sys
import threading
import random
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from issues.models import Issue
from accounts.models import User, Location, Department

def create_issue_worker(i, location, department, citizen):
    try:
        issue = Issue.objects.create(
            title=f"Stress Test Issue {i} - {random.randint(1000, 9999)}",
            category="pothole",
            department=department,
            location=location,
            reported_by=citizen,
            status="pending"
        )
        return True, issue.id
    except Exception as e:
        return False, str(e)

def run_stress_test():
    print("--- CONCURRENCY STRESS TEST ---")
    ward = Location.objects.get(name='Wadgaon Sheri', type='ward')
    pwd = Department.objects.get(id=11)
    citizen = User.objects.filter(role='citizen').first()
    
    num_issues = 30
    success_count = 0
    failures = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_issue_worker, i, ward, pwd, citizen) for i in range(num_issues)]
        for f in futures:
            success, result = f.result()
            if success:
                success_count += 1
            else:
                failures.append(result)
                
    print(f"Successfully created: {success_count}/{num_issues}")
    if failures:
        print(f"Failures encountered: {failures[:5]}")
        
    # Validation
    issues = Issue.objects.filter(title__startswith="Stress Test Issue")
    null_assigns = issues.filter(assigned_to__isnull=True).count()
    print(f"Total test issues stored: {issues.count()}")
    print(f"Null assignments (if 0, assignment was perfectly atomic): {null_assigns}")

    # Cleanup
    issues.delete()

if __name__ == "__main__":
    run_stress_test()
