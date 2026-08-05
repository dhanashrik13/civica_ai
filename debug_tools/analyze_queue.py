import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask
from django.db.models import Count

print("=== Task Queue Analysis ===")
task_counts = PendingTask.objects.values('task_name').annotate(count=Count('id')).order_by('-count')
for tc in task_counts:
    print(f"{tc['task_name']}: {tc['count']}")

print("\n=== Sample Duplicate Tasks ===")
duplicates = PendingTask.objects.values('task_name', 'args', 'kwargs').annotate(count=Count('id')).filter(count__gt=1)[:10]
for d in duplicates:
    print(f"Task: {d['task_name']}, Args: {d['args']}, Count: {d['count']}")
