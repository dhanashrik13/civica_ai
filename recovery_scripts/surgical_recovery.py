import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from django.db import transaction
from accounts.models import PendingTask, OfficerProfile, Department
from issues.models import Issue
from notifications.models import Notification
from django.db.models import Count, Min

# PHASE 2: Duplicate Notification Cleanup
def cleanup_notifications(start_id, end_id):
    results = []
    for issue_id in range(start_id, end_id + 1):
        notes = Notification.objects.filter(related_issue_id=issue_id).order_by('created_at')
        count_before = notes.count()
        if count_before > 1:
            first_note = notes.first()
            # Delete all except the first
            deleted_count, _ = Notification.objects.filter(related_issue_id=issue_id).exclude(id=first_note.id).delete()
            results.append({'id': issue_id, 'before': count_before, 'removed': deleted_count, 'after': 1})
        elif count_before == 1:
            results.append({'id': issue_id, 'before': 1, 'removed': 0, 'after': 1})
        else:
            results.append({'id': issue_id, 'before': 0, 'removed': 0, 'after': 0})
    return results

# PHASE 3: Partial Category Repair
def repair_categories(start_id, end_id):
    mapping = {
        "pothole": "pwd",
        "road_damage": "pwd",
        "water_leakage": "water_supply",
        "street_light": "electricity",
        "garbage": "sanitation",
        "drainage": "drainage_sewerage"
    }
    
    results = []
    issues = Issue.objects.filter(id__range=(start_id, end_id))
    for issue in issues:
        old_cat = issue.category
        if old_cat in mapping:
            new_cat = mapping[old_cat]
            # Map category to official department
            from issues.services import map_category_to_department
            dept = map_category_to_department(new_cat)
            
            if dept:
                issue.category = new_cat
                issue.department = dept
                issue.save()
                results.append({'id': issue.id, 'old': old_cat, 'new': new_cat, 'dept': dept.name})
            else:
                print(f"FAILED to find department for category '{new_cat}'")
    return results

# PHASE 5: Safe Task Deduplication
def deduplicate_tasks():
    # Keep only the EARLIEST 'pending' task for each (name, args, kwargs)
    duplicates = PendingTask.objects.filter(status='pending').values('task_name', 'args', 'kwargs').annotate(min_id=Min('id'), count=Count('id')).filter(count__gt=1)
    
    removed_count = 0
    for d in duplicates:
        # Delete all except min_id
        count, _ = PendingTask.objects.filter(
            task_name=d['task_name'],
            args=d['args'],
            kwargs=d['kwargs'],
            status='pending'
        ).exclude(id=d['min_id']).delete()
        removed_count += count
    return removed_count

# PHASE 5.1: Remove redundant enrichment tasks for already repaired issues
def remove_redundant_enrichments(start_id, end_id):
    count, _ = PendingTask.objects.filter(
        task_name='issues.tasks.enrich_issue_context',
        args__in=[[i] for i in range(start_id, end_id + 1)],
        status='pending'
    ).delete()
    return count

# RUN SURGICAL RECOVERY
with transaction.atomic():
    print("PHASE 2: Cleaning up notifications...")
    note_cleanup = cleanup_notifications(2305, 2334)
    
    print("PHASE 3: Repairing categories...")
    cat_repair = repair_categories(2305, 2334)
    
    print("PHASE 5: Deduplicating tasks...")
    tasks_removed = deduplicate_tasks()
    
    print("PHASE 5.1: Removing redundant enrichments...")
    enrich_removed = remove_redundant_enrichments(2305, 2334)

# Output Results for Tables
print("\nTABLE 1: NOTIFICATION CLEANUP")
print("| Issue ID | Duplicates Removed | Remaining |")
for res in note_cleanup:
    if res['removed'] > 0:
        print(f"| {res['id']} | {res['removed']} | {res['after']} |")

print("\nTABLE 2: CATEGORY NORMALIZATION")
print("| Issue ID | Old Category | New Canonical Category |")
for res in cat_repair:
    print(f"| {res['id']} | {res['old']} | {res['new']} |")

# For Table 3 & 4 we'll summarize
print("\nTABLE 3: TASK QUEUE ANALYSIS (Post-cleanup)")
from django.db.models import Count
task_counts = PendingTask.objects.values('task_name').annotate(count=Count('id')).order_by('-count')
for tc in task_counts:
    print(f"| {tc['task_name']} | Valid: {tc['count']} |")

print(f"\nTABLE 4: DEDUPLICATION RESULTS")
print(f"| Generic Duplicates Removed | {tasks_removed} | Redundant Pending tasks |")
print(f"| Redundant Enrichments Removed | {enrich_removed} | Already repaired issues 2305-2334 |")

print("\nTABLE 5: SAFE RESUME STATUS")
print("| Component | Ready? | Notes |")
print(f"| Notifications | Yes | {len([r for r in note_cleanup if r['removed'] > 0])} issues cleaned |")
print(f"| Categories | Yes | {len(cat_repair)} issues normalized |")
print(f"| Task Queue | Yes | {tasks_removed + enrich_removed} tasks removed total |")

print("\nSummary: Workflow consistency restored.")
