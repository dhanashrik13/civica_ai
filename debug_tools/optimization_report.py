import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import PendingTask, User
from notifications.models import Notification
from issues.models import Issue
from django.db.models import Count
from django.utils import timezone

# 1. Dashboard N+1 Analysis
# Top Bottlenecks:
# - get_active_citizens: O(N) where N is number of departments.
# - get_officer_performance_stats: O(N) where N is number of officers (due to SLA check in python loop).
# - citizen_dashboard: Values(500) is better than full objects, but still does multiple related lookups.

# 2. Query Analysis
print("=== Query Analysis Summary ===")
# identified:
# - Prefetch unresolved_issues in get_officer_performance_stats is good, but is_overdue property 
#   still accesses related fields (sla_multiplier, created_at, priority). 
# - is_overdue accesses self.sla_days which accesses self.priority and self.sla_multiplier.
# - sla_multiplier is a field on Issue (from my previous read).

# 3. Queue Analysis
print("\n=== Queue Analysis Summary ===")
task_counts = PendingTask.objects.values('task_name').annotate(count=Count('id')).order_by('-count')
for tc in task_counts:
    print(f"{tc['task_name']}: {tc['count']}")

# 4. Debounce Strategy
# - Metric tasks: Group by [officer_id] and keep only latest.
# - Citizen tasks: Group by [user_id] and keep only latest.
# - Projection tasks: Group by [event_id] (but events are unique, so this is about sequence).

print("\n=== Optimization Plan Proposed ===")
print("1. [DASHBOARD] Optimize get_active_citizens with a single grouped query or prefetch.")
print("2. [DASHBOARD] Add sla_days to get_officer_performance_stats values/annotation to move SLA check to DB.")
print("3. [QUEUE] Implement generic task debouncing in dispatch_task_transactional to prevent redundant metric tasks.")
print("4. [QUEUE] Add priority routing for high-impact tasks (enrichment vs analytics).")
print("5. [INDEXING] Verify/Add composite indexes for (district, department) and (status, priority).")

# 5. Measure Latency (Simulated)
# current latencies:
# get_issue_counts: 0.0089s
# get_map_points: 0.0012s
# get_active_citizens: 0.0171s (with 11 queries)
