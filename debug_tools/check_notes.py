import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from notifications.models import Notification
notes = Notification.objects.filter(related_issue_id=2330).order_by('created_at')
for n in notes:
    print(f"ID: {n.id}, Type: {n.type}, Created: {n.created_at}")
