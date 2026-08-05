import os
import django
import json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask, OfficerProfile
from django.db.models import Count

print("=== DEBOUNCE AUDIT ===")
# Tasks are stored with JSON args, so we need to match exactly or use JSON field lookups
# But values('args') should work if the exact JSON string matches.

duplicates = PendingTask.objects.filter(status='pending', task_name='accounts.tasks.recalculate_officer_metrics').values('args').annotate(count=Count('id')).filter(count__gt=1).order_by('-count')
print(f"Officer metric tasks needing debouncing: {duplicates.count()}")
for d in duplicates[:5]:
    print(f"Officer {d['args']}: {d['count']} pending tasks")

citizen_duplicates = PendingTask.objects.filter(status='pending', task_name='accounts.tasks.sync_citizen_profile_counters').values('args').annotate(count=Count('id')).filter(count__gt=1).order_by('-count')
print(f"\nCitizen counter tasks needing debouncing: {citizen_duplicates.count()}")
for d in citizen_duplicates[:5]:
    print(f"Citizen {d['args']}: {d['count']} pending tasks")
