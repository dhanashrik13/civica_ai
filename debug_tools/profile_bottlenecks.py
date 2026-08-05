import os
import django
import time
from django.db import connection, reset_queries

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from issues.models import Issue
from dashboards.services import get_issue_counts, get_map_points, get_activity_feed, get_active_citizens
from accounts.models import User

def profile_call(func, *args, **kwargs):
    reset_queries()
    start_time = time.time()
    result = func(*args, **kwargs)
    duration = time.time() - start_time
    query_count = len(connection.queries)
    return duration, query_count

# Find a representative user (e.g., an officer or admin)
user = User.objects.filter(role=User.Role.OFFICER).first() or User.objects.first()

print(f"Profiling for user: {user.username} (Role: {user.role})")
print("-" * 50)

# 1. get_issue_counts
duration, q_count = profile_call(get_issue_counts, user)
print(f"get_issue_counts: {duration:.4f}s, {q_count} queries")

# 2. get_map_points
duration, q_count = profile_call(get_map_points, user)
print(f"get_map_points: {duration:.4f}s, {q_count} queries")

# 3. get_activity_feed
duration, q_count = profile_call(get_activity_feed, user)
print(f"get_activity_feed: {duration:.4f}s, {q_count} queries")

# 4. get_active_citizens
duration, q_count = profile_call(get_active_citizens, user)
print(f"get_active_citizens: {duration:.4f}s, {q_count} queries")

# 5. Issue creation overhead (minimal)
def create_issue_sim():
    with connection.cursor() as cursor:
         # We just want to see how many queries a typical save might trigger if we could, 
         # but let's just count existing ones.
         pass

print("-" * 50)
print("N+1 Detection in Activity Feed:")
reset_queries()
get_activity_feed(user)
for q in connection.queries:
    print(f"QUERY: {q['sql'][:100]}...")
