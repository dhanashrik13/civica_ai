import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask

t = PendingTask.objects.filter(task_name='accounts.tasks.recalculate_officer_metrics', status='dispatched').first()
if t:
    print(f"Dispatched ID: {t.id}, Args: {t.args}")
else:
    print("No dispatched tasks found for metrics.")
