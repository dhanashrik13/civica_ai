import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask
from django.db.models import Count

duplicates = PendingTask.objects.filter(status='dispatched', task_name='accounts.tasks.recalculate_officer_metrics').values('args').annotate(count=Count('id')).filter(count__gt=1).order_by('-count')
print(f"Dispatched metric duplicates: {duplicates.count()}")
for d in duplicates[:5]:
    print(f"Officer {d['args']}: {d['count']} tasks")
