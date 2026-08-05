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
# Mock full_name in a values call if it causes issues, but let's try with username first
# Actually, the error was because I used 'reported_by__full_name' which is a property, not a field.

def get_active_citizens_v2(user, limit=5, department=None):
    from django.db.models import Max, Count, Q
    from accounts.utils import apply_rbac_filter
    from accounts.models import Department
    
    citizen_issues = apply_rbac_filter(Issue.objects.all(), user).filter(
        reported_by__role=User.Role.CITIZEN
    )
    
    if department:
        citizen_issues = citizen_issues.filter(department=department)

    dept_ids = citizen_issues.values_list('department', flat=True).distinct()
    depts = Department.objects.filter(id__in=dept_ids).order_by('name')

    results = []
    for dept in depts:
        citizens = citizen_issues.filter(department=dept).values(
            'reported_by__id', 
            'reported_by__username', 
        ).annotate(
            report_count=Count('id'),
            last_activity=Max('created_at')
        ).order_by('-report_count')[:limit]
        
        if citizens:
            results.append({
                'department': dept,
                'citizens': list(citizens)
            })
            
    return results

reset_queries()
get_active_citizens_v2(user)
print(f"get_active_citizens queries: {len(connection.queries)}")

from dashboards.views import citizen_dashboard
from django.test import RequestFactory
factory = RequestFactory()
citizen = User.objects.filter(role=User.Role.CITIZEN).first()
if citizen:
    request = factory.get('/citizen/dashboard/')
    request.user = citizen
    reset_queries()
    citizen_dashboard(request)
    print(f"citizen_dashboard queries: {len(connection.queries)}")
    # Detect N+1 by looking for repeated queries
    query_sqls = [q['sql'] for q in connection.queries if "SELECT" in q['sql']]
    print(f"Total SELECT queries: {len(query_sqls)}")
    unique_queries = set(query_sqls)
    print(f"Unique SELECT queries: {len(unique_queries)}")
    if len(query_sqls) > len(unique_queries):
        print("POTENTIAL N+1 DETECTED!")
