import os
import django
import time
from django.db import connection, reset_queries

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from issues.models import Issue
from accounts.models import User

# Find a superuser/admin to see more data
user = User.objects.filter(role=User.Role.SUPER_ADMIN).first() or User.objects.first()

print(f"Profiling for user: {user.username} (Role: {user.role})")

from dashboards.services import get_active_citizens
reset_queries()
get_active_citizens(user)
print(f"get_active_citizens queries: {len(connection.queries)}")
# for q in connection.queries:
#     print(f"QUERY: {q['sql'][:120]}...")

from dashboards.views import citizen_dashboard
from django.test import RequestFactory
factory = RequestFactory()
# Citizen user
citizen = User.objects.filter(role=User.Role.CITIZEN).first()
if citizen:
    request = factory.get('/citizen/dashboard/')
    request.user = citizen
    reset_queries()
    citizen_dashboard(request)
    print(f"citizen_dashboard queries: {len(connection.queries)}")
    for q in connection.queries:
        if "SELECT" in q['sql']:
             print(f"QUERY: {q['sql'][:120]}...")
