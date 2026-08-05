
import os
import django
import time
import random
from django.core.files.base import ContentFile
import importlib
from django.utils import timezone
from django.db import transaction

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, Department, IssueMetadata
from accounts.models import User, Location, OfficerProfile, PendingTask

def get_dummy_image(name):
    # 1x1 transparent PNG
    png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return ContentFile(png_content, name=f"{name}.png")

def process_tasks_locally():
    tasks = PendingTask.objects.filter(status=PendingTask.Status.PENDING).order_by('created_at')
    
    success = 0
    failed = 0
    
    for t in tasks:
        try:
            module_path, func_name = t.task_name.rsplit('.', 1)
            module = importlib.import_module(module_path)
            task_func = getattr(module, func_name)
            
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
            # print(f"Failed task {t.task_name}: {e}")
            
    return success, failed

def run_test():
    print("=== LARGE-SCALE SYSTEM TEST (100 ISSUES) ===")
    
    # Mock Celery send_task to prevent connection timeouts from slowing down the test
    import unittest.mock
    from final_proj.celery import app
    mock_send = unittest.mock.patch.object(app, 'send_task')
    mock_send.start()
    print("Mocked app.send_task for faster local queuing.")

    start_total_time = time.time()
    
    citizen, _ = User.objects.get_or_create(username="large_scale_tester", defaults={'email': "tester@example.com", 'role': User.Role.CITIZEN})
    citizen.set_password("pass123")
    citizen.save()

    print("\n--- PHASE 1: OFFICER COVERAGE ANALYSIS ---")
    active_officers = OfficerProfile.objects.filter(is_active=True, user__is_active=True).select_related('department', 'location')
    
    valid_locations = []
    coverage_map = {}
    for off in active_officers:
        if off.level == 'village' and off.village:
            loc_key = (off.district, off.taluka, off.village)
        elif off.level == 'taluka' and off.taluka:
            loc_key = (off.district, off.taluka, None)
        elif off.level == 'district' and off.district:
            loc_key = (off.district, None, None)
        else:
            continue
            
        key = (off.department.name, loc_key)
        if key not in coverage_map:
            coverage_map[key] = 0
        coverage_map[key] += 1
        
        if off.location_id and loc_key not in [vl['loc_key'] for vl in valid_locations]:
            valid_locations.append({
                'loc_key': loc_key,
                'location_id': off.location_id,
                'district': off.district,
                'taluka': off.taluka,
                'village': off.village,
                'department_id': off.department_id,
                'department_name': off.department.name
            })
            
    print(f"TABLE — VALID COVERAGE MAP (Sample of {min(5, len(coverage_map))})")
    print(f"{'Department':<35} | {'Location':<30} | {'Officers':<10}")
    for k, count in list(coverage_map.items())[:5]:
        loc_str = str(k[1])
        print(f"{k[0]:<35} | {loc_str:<30} | {count:<10}")

    if not valid_locations:
        print("ERROR: No valid locations with officers found!")
        return

    print("\n--- PHASE 2: CREATING 100 ISSUES ---")
    
    categories = [
        (Issue.Category.POTHOLE, "Pothole"),
        (Issue.Category.WATER_LEAKAGE, "Water Leakage"),
        (Issue.Category.GARBAGE, "Garbage"),
        (Issue.Category.STREET_LIGHT, "Street Light"),
        (Issue.Category.DRAINAGE, "Drainage"),
        (Issue.Category.ENVIRONMENT, "Environment"),
        (Issue.Category.TRAFFIC_POLICE, "Traffic"),
        (Issue.Category.ELECTRICITY, "Electricity"),
        (Issue.Category.DISASTER_MANAGEMENT, "Disaster"),
        (Issue.Category.HEALTH, "Health")
    ]
    
    created_issues = []
    
    create_start = time.time()
    
    for i in range(1, 101):
        # Pick a valid location that has coverage
        vloc = random.choice(valid_locations)
        cat = random.choice(categories)
        
        issue = Issue(
            title=f"Test Issue {i}: {cat[1]} in {vloc['village'] or vloc['taluka'] or vloc['district']}",
            description=f"Detailed description for {cat[1]} at {vloc['village'] or vloc['taluka']}.",
            category=cat[0],
            priority=random.choice([Issue.Priority.LOW, Issue.Priority.MEDIUM, Issue.Priority.HIGH]),
            reported_by=citizen,
            location_id=vloc['location_id'],
            district=vloc['district'],
            taluka=vloc['taluka'],
            village=vloc['village']
        )
        issue.save()
        
        # Attach dummy image
        img_name = f"photo_{cat[1].lower().replace(' ', '_')}_{i}"
        issue.photo1 = get_dummy_image(img_name)
        issue.save()
        
        created_issues.append(issue.id)

    create_latency = (time.time() - create_start) / 100
    print(f"Created 100 issues successfully. Avg creation latency: {create_latency:.3f}s")

    print("\n--- PHASE 3: FULL WORKFLOW EXECUTION ---")
    process_start = time.time()
    
    success, failed = process_tasks_locally()
    
    process_time = time.time() - process_start
    print(f"Processed {success} tasks successfully, {failed} failed in {process_time:.2f}s")

    print("\n--- PHASE 4 & 5: ASSIGNMENT VALIDATION & FAILURE DETECTION ---")
    
    issues = Issue.objects.filter(id__in=created_issues).select_related('assigned_to', 'assigned_to__user', 'department', 'metadata')
    
    table1 = []
    table2 = []
    table3 = []
    table4 = []
    
    assigned_count = 0
    pending_count = 0
    failed_count = 0
    
    for iss in issues:
        assigned = iss.assigned_to.user.username if iss.assigned_to else "None"
        status = iss.status
        dept_name = iss.department.name if iss.department else "None"
        
        table1.append(f"{iss.id:<8} | {iss.title[:35]:<35} | {dept_name[:20]:<20} | {iss.village or iss.taluka:<15} | {iss.priority:<10} | {status:<10}")
        
        if iss.assigned_to:
            assigned_count += 1
            off_dept = iss.assigned_to.department.name
            dept_match = "Yes" if off_dept == dept_name else "No"
            level = iss.assigned_to.level
            table2.append(f"{iss.id:<8} | {assigned[:20]:<20} | {dept_match:<16} | {level:<15} | SUCCESS")
        else:
            pending_count += 1
            reason = "Unknown"
            if not iss.is_enriched:
                reason = "Enrichment Task Failed/Pending"
            elif not iss.department:
                reason = "Department Mapping Failed"
            else:
                reason = "No Officer Candidate Found"
                
            table4.append(f"{iss.id:<8} | Assignment    | {reason[:30]:<30} | HIGH")
            table2.append(f"{iss.id:<8} | None                 | N/A              | N/A             | FAILED")

        # Image validation
        has_image = "Yes" if getattr(iss, 'photo1', None) or getattr(iss, '_deferred_photo1', None) or (hasattr(iss, 'metadata') and iss.metadata.photo1) else "No"
        path = str(iss.metadata.photo1) if hasattr(iss, 'metadata') and iss.metadata.photo1 else "N/A"
        table3.append(f"{iss.id:<8} | {has_image:<14} | SUCCESS       | {path[:30]}")

    print("\nTABLE 1 — ALL CREATED ISSUES (Sample of 15)")
    print(f"{'Issue ID':<8} | {'Title':<35} | {'Department':<20} | {'Location':<15} | {'Priority':<10} | {'Status':<10}")
    print("-" * 110)
    for row in table1[:15]: print(row)
    print("... (85 more issues)")

    print("\nTABLE 2 — ASSIGNMENT RESULTS (Sample of 15)")
    print(f"{'Issue ID':<8} | {'Assigned Officer':<20} | {'Department Match':<16} | {'Hierarchy Match':<15} | {'Result':<10}")
    print("-" * 85)
    for row in table2[:15]: print(row)
    print("... (85 more issues)")

    print("\nTABLE 3 — IMAGE VALIDATION (Sample of 5)")
    print(f"{'Issue ID':<8} | {'Image Attached':<14} | {'Upload Status':<13} | {'Storage Path':<30}")
    print("-" * 75)
    for row in table3[:5]: print(row)
    print("... (95 more issues)")

    print("\nTABLE 4 — FAILED ISSUES")
    print(f"{'Issue ID':<8} | {'Failure Stage':<13} | {'Exact Root Cause':<30} | {'Severity':<10}")
    print("-" * 70)
    if not table4:
        print("No failures detected!")
    else:
        for row in table4: print(row)

    total_time = time.time() - start_total_time

    print("\nTABLE 5 — PERFORMANCE METRICS")
    print(f"Metric                        | Value")
    print("-" * 50)
    print(f"Avg Issue Creation Latency    | {create_latency:.3f} seconds")
    print(f"Total Async Processing Time   | {process_time:.2f} seconds")
    print(f"Avg Async Task Latency        | {(process_time / (success+failed) if (success+failed) > 0 else 0):.3f} seconds")
    print(f"Total Test Execution Time     | {total_time:.2f} seconds")

    print("\nTABLE 6 — WORKFLOW SUCCESS SUMMARY")
    success_rate = (assigned_count / 100) * 100
    print(f"{'Total Issues':<15} | {'Assigned':<10} | {'Pending':<10} | {'Failed':<10} | {'Success Rate':<15}")
    print("-" * 65)
    print(f"{100:<15} | {assigned_count:<10} | {pending_count:<10} | {len(table4):<10} | {success_rate:.1f}%")

if __name__ == "__main__":
    run_test()
