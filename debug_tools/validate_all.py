
import os
import django
import sys
from django.db.models import Count

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import Location, OfficerProfile
from issues.models import Issue

def check_hierarchy():
    print("--- Hierarchy Check ---")
    orphans = Location.objects.filter(parent__isnull=True).exclude(type='district')
    print(f"Orphans (should be 0): {orphans.count()}")

def check_assignments():
    print("--- Assignment Check ---")
    null_assigns = Issue.objects.filter(assigned_to__isnull=True).count()
    print(f"Null assignments: {null_assigns}")

    cross_jurisdictions = 0
    # Quick check for clear cross-jurisdictions (where officer is not in issue's ancestry)
    issues = Issue.objects.filter(assigned_to__isnull=False, location__isnull=False)[:50]
    for issue in issues:
        valid = False
        curr = issue.location
        while curr:
            if curr.id == issue.assigned_to.location_id:
                valid = True
                break
            curr = curr.parent
        if not valid:
            cross_jurisdictions += 1
            
    print(f"Sampled Cross Jurisdictions: {cross_jurisdictions} out of {issues.count()}")

if __name__ == "__main__":
    check_hierarchy()
    check_assignments()
