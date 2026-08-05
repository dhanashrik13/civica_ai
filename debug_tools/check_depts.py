import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import Department
for d in Department.objects.all():
    print(f"'{d.name}'")
