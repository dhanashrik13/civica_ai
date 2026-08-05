
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, OfficerProfile, CitizenProfile, AdminProfile
from django.db import connection, reset_queries

def audit_profiles():
    print("--- Profile Integrity Audit ---")
    users = User.objects.all()
    total_users = users.count()
    print(f"Total Users: {total_users}")

    missing_profile = []
    orphans = {
        "OfficerProfile": [],
        "CitizenProfile": [],
        "AdminProfile": []
    }

    for user in users:
        if user.role == User.Role.CITIZEN:
            if not hasattr(user, 'citizen_profile'):
                missing_profile.append((user.id, user.username, user.role))
        elif user.role == User.Role.OFFICER:
            if not hasattr(user, 'officer'):
                missing_profile.append((user.id, user.username, user.role))
        elif user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN]:
            if not hasattr(user, 'admin_profile'):
                missing_profile.append((user.id, user.username, user.role))

    print(f"Users missing profiles: {len(missing_profile)}")
    for m in missing_profile:
        print(f"  - User {m[0]} ({m[1]}) Role: {m[2]}")

    # Check for orphans
    for op in OfficerProfile.objects.all():
        try:
            op.user
        except User.DoesNotExist:
            orphans["OfficerProfile"].append(op.id)
    
    for cp in CitizenProfile.objects.all():
        try:
            cp.user
        except User.DoesNotExist:
            orphans["CitizenProfile"].append(cp.id)

    for ap in AdminProfile.objects.all():
        try:
            ap.user
        except User.DoesNotExist:
            orphans["AdminProfile"].append(ap.id)

    print(f"Orphaned Profiles: {orphans}")

def audit_bridges():
    print("\n--- Compatibility Bridge Stress Test ---")
    reset_queries()
    users = User.objects.all()[:10]
    print(f"Testing bridges for 10 users...")
    
    start_queries = len(connection.queries)
    for user in users:
        _ = user.full_name
        _ = user.department
        _ = user.phone_no
        _ = user.address
    end_queries = len(connection.queries)
    
    print(f"Queries triggered by property access (unoptimized): {end_queries - start_queries}")
    
    reset_queries()
    users_optimized = User.objects.select_related('officer', 'citizen_profile', 'admin_profile', 'officer__department', 'admin_profile__department').all()[:10]
    start_queries = len(connection.queries)
    for user in users_optimized:
        _ = user.full_name
        _ = user.department
        _ = user.phone_no
        _ = user.address
    end_queries = len(connection.queries)
    print(f"Queries triggered by property access (optimized): {end_queries - start_queries}")

if __name__ == "__main__":
    audit_profiles()
    audit_bridges()
