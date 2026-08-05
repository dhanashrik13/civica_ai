import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, OfficerProfile, Location
from issues.models import Issue

username = "amit.jadhav.340"
try:
    user = User.objects.get(username=username)
    profile = OfficerProfile.objects.select_related('department', 'location').get(user=user)
    
    print("=== TABLE 1: OFFICER PROFILE ===")
    print(f"| Field | Value |")
    print(f"| Username | {user.username} |")
    print(f"| Full Name | {user.full_name} |")
    print(f"| Role | {user.role} |")
    print(f"| Department | {profile.department.name} |")
    print(f"| Level | {profile.level} |")
    print(f"| Active | {profile.is_active} |")
    
    print("\n=== TABLE 2: LOCATION HIERARCHY ===")
    print("| Level | Value | Valid? |")
    
    def get_valid_status(loc_name, expected_type, parent=None):
        if not loc_name: return "N/A"
        matches = Location.objects.filter(name__iexact=loc_name, type=expected_type)
        if parent:
            matches = matches.filter(parent=parent)
        return "Yes" if matches.exists() else "No (Mismatch/Missing)"

    # Trace hierarchy from the linked Location object
    curr = profile.location
    hierarchy = []
    while curr:
        hierarchy.append(curr)
        curr = curr.parent
    
    # Map by type
    h_map = {loc.type: loc for loc in hierarchy}
    
    for lvl in ['village', 'ward', 'taluka', 'zone', 'city', 'district']:
        val = getattr(profile, lvl, "")
        canonical = h_map.get(lvl)
        is_valid = "Yes" if (canonical and canonical.name.lower() == str(val).lower()) else "No"
        if not val and not canonical:
             print(f"| {lvl.title()} | (Empty) | N/A |")
        else:
             print(f"| {lvl.title()} | {val} (Canonical: {canonical.name if canonical else 'None'}) | {is_valid} |")

    print("\n=== TABLE 3: JURISDICTION VALIDATION ===")
    # Check if string fields on Profile match the linked Location hierarchy
    linked_dist = h_map.get('district')
    dist_match = "Yes" if (linked_dist and linked_dist.name == profile.district) else "No"
    
    print(f"| Check | Result |")
    print(f"| Linked Location Exists | {'Yes' if profile.location else 'No'} |")
    print(f"| District String Sync | {dist_match} |")
    print(f"| Orphan Check | {'Safe' if (profile.location and (profile.location.type == 'district' or profile.location.parent)) else 'Orphaned'} |")

    print("\n=== TABLE 4: ASSIGNED ISSUES ===")
    print("| Issue ID | Issue Location | Valid Assignment? |")
    assigned = Issue.objects.filter(assigned_to=profile)
    for iss in assigned:
        # Simple validation: Does issue district match officer district?
        is_valid = "Yes" if iss.district == profile.district else "No (Leakage!)"
        # Deeper check: Does department match?
        if iss.department_id != profile.department_id:
            is_valid += " / Dept Mismatch"
        
        print(f"| {iss.id} | {iss.district} > {iss.taluka or iss.city} | {is_valid} |")
    
    if not assigned.exists():
        print("| None | N/A | N/A |")

except User.DoesNotExist:
    print(f"Error: User {username} not found.")
except OfficerProfile.DoesNotExist:
    print(f"Error: OfficerProfile for {username} not found.")
except Exception as e:
    print(f"Error: {e}")
