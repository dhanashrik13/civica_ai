import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask
from django.db.models import Count

tasks = PendingTask.objects.filter(status='pending', task_name='accounts.tasks.recalculate_officer_metrics')
print(f"Total pending recalculate tasks: {tasks.count()}")
for t in tasks[:10]:
    print(f"ID: {t.id}, Args: {t.args}, Type: {type(t.args)}")

# Manual group by
groups = {}
for t in tasks:
    key = str(t.args)
    groups[key] = groups.get(key, 0) + 1

sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)
print("\nGroups by str(args):")
for k, v in sorted_groups[:10]:
    print(f"{k}: {v}")
