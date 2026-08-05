import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from notifications.models import Notification
from issues.models import Issue
from django.db.models import Count

print("=== Verification of Cleanup ===")
issues = Issue.objects.filter(id__range=(2305, 2334))
duplicate_notes = Notification.objects.filter(related_issue_id__in=range(2305,2335)).values('related_issue_id').annotate(c=Count('id')).filter(c__gt=1)
print(f"Issues with duplicate notifications: {duplicate_notes.count()}")

partially_repaired = issues.filter(category__in=['pothole', 'road_damage', 'water_leakage', 'street_light', 'garbage', 'drainage']).count()
print(f"Issues with legacy categories: {partially_repaired}")

from accounts.models import PendingTask
duplicates = PendingTask.objects.filter(status='pending').values('task_name', 'args', 'kwargs').annotate(count=Count('id')).filter(count__gt=1).count()
print(f"Duplicate pending tasks: {duplicates}")
