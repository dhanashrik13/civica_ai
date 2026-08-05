
import os
import django
import time
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, Department
from accounts.models import User, Location, OfficerProfile
from accounts.utils_async import recover_pending_tasks

import importlib
from django.utils import timezone
from django.db import transaction

def process_tasks_locally():
    from accounts.models import PendingTask
    tasks = PendingTask.objects.filter(status=PendingTask.Status.PENDING).order_by('created_at')
    total = tasks.count()
    print(f"--- Processing {total} pending tasks locally ---")
    
    success = 0
    failed = 0
    
    for t in tasks:
        try:
            # Dynamically import the task function
            module_path, func_name = t.task_name.rsplit('.', 1)
            module = importlib.import_module(module_path)
            task_func = getattr(module, func_name)
            
            # Execute the function (unwrap shared_task if needed)
            if hasattr(task_func, 'run'):
                task_func.run(*t.args, **t.kwargs)
            else:
                task_func(*t.args, **t.kwargs)
                
            with transaction.atomic():
                PendingTask.objects.filter(pk=t.pk).update(
                    status=PendingTask.Status.DISPATCHED,
                    dispatched_at=timezone.now()
                )
            success += 1
        except Exception as e:
            failed += 1
            print(f"FAILED: {t.task_name} - {str(e)}")
            
    print(f"--- Finished: {success} Success, {failed} Failed ---")

def run_stress_test():
    print("--- PHASE 1: ISSUE CREATION ---")
    
    citizen = User.objects.filter(role=User.Role.CITIZEN).first()
    if not citizen:
        citizen = User.objects.create_user(username="test_citizen_stress", email="stress@example.com", password="password123", role=User.Role.CITIZEN)

    locations = ["Padali Ranjangaon", "Kashti"]
    
    # Define 10 issue templates
    issue_templates = [
        {"title": "Pothole on Main Road", "category": Issue.Category.POTHOLE, "desc": "Large pothole causing accidents near the entrance."},
        {"title": "Major Water Leakage", "category": Issue.Category.WATER_LEAKAGE, "desc": "Main pipeline burst, water flooding the street."},
        {"title": "Garbage Overflow at Market", "category": Issue.Category.GARBAGE, "desc": "Bins haven't been cleared for 3 days. Foul smell."},
        {"title": "Street Light Failure", "category": Issue.Category.STREET_LIGHT, "desc": "Entire block is in dark for two nights."},
        {"title": "Drainage Blockage", "category": Issue.Category.DRAINAGE, "desc": "Sewage water overflowing from manhole."},
        {"title": "Illegal Dumping", "category": Issue.Category.ENVIRONMENT, "desc": "Construction waste being dumped in the open field."},
        {"title": "Traffic Signal Malfunction", "category": Issue.Category.TRAFFIC_POLICE, "desc": "Signals at the main junction are stuck on red."},
        {"title": "Tree Fallen on Electric Line", "category": Issue.Category.ELECTRICITY, "desc": "Dangerous situation after storm, sparks flying."},
        {"title": "Flood Risk in Low Area", "category": Issue.Category.DISASTER_MANAGEMENT, "desc": "Water level rising rapidly after heavy rain."},
        {"title": "Mosquito Breeding Site", "category": Issue.Category.HEALTH, "desc": "Stagnant water in open plots causing health risk."}
    ]

    created_ids = []

    for loc_name in locations:
        loc = Location.objects.filter(name__iexact=loc_name).first()
        if not loc:
            print(f"Creating missing location: {loc_name}")
            dist = Location.objects.get_or_create(name="Ahmednagar", type="district")[0]
            tal = Location.objects.get_or_create(name="Parner" if loc_name == "Padali Ranjangaon" else "Shrigonda", type="taluka", parent=dist)[0]
            loc = Location.objects.create(name=loc_name, type="village", parent=tal)
            
        print(f"Creating 10 issues in {loc_name}...")
        for template in issue_templates:
            start_time = time.time()
            issue = Issue.objects.create(
                title=f"{template['title']} ({loc_name})",
                description=template['desc'],
                category=template['category'],
                reported_by=citizen,
                location=loc
            )
            save_time = time.time() - start_time
            created_ids.append(issue.id)
            print(f"  Created Issue #{issue.id}: {issue.title} (Save: {save_time:.3f}s)")

    print(f"\n--- PHASE 2 & 3: PROCESSING & AUDIT ---")
    print("Simulating async processing (Processing tasks locally for verification)...")
    
    # We'll process them locally since we know the broker is likely down/backlogged
    # This ensures the 'stress test' actually finishes its workflow
    process_tasks_locally()

    # Re-fetch issues to see updated state
    issues = Issue.objects.filter(id__in=created_ids).select_related('assigned_to', 'assigned_to__user', 'department')
    
    audit_data = []
    for iss in issues:
        audit_data.append(iss)

    print("\nTABLE 1 — CREATED ISSUES & TABLE 2 — ASSIGNMENT RESULTS")
    print(f"{'ID':<6} | {'Title':<40} | {'Dept':<25} | {'Location':<20} | {'Assigned To':<20} | {'Result':<10}")
    print("-" * 135)
    for iss in audit_data:
        assigned = iss.assigned_to.user.username if iss.assigned_to else "Not Assigned"
        dept_name = iss.department.name if iss.department else "None"
        result = "SUCCESS" if iss.assigned_to else "FAILED"
        print(f"{iss.id:<6} | {iss.title[:40]:<40} | {dept_name[:25]:<25} | {iss.village:<20} | {assigned:<20} | {result:<10}")

    print("\nTABLE 4 — HIERARCHY FALLBACK ANALYSIS")
    print(f"{'ID':<6} | {'Village':<20} | {'Taluka':<20} | {'District':<20} | {'Fallback Level':<15}")
    print("-" * 90)
    for iss in audit_data:
        level = iss.assigned_to.level if iss.assigned_to else "N/A"
        print(f"{iss.id:<6} | {iss.village:<20} | {iss.taluka:<20} | {iss.district:<20} | {level:<15}")

    print("\nTABLE 5 — ASYNC PIPELINE STATUS")
    print(f"{'ID':<6} | {'Enriched':<10} | {'Explanation'}")
    print("-" * 100)
    for iss in audit_data:
        print(f"{iss.id:<6} | {str(iss.is_enriched):<10} | {iss.assignment_explanation}")

if __name__ == "__main__":
    run_stress_test()
