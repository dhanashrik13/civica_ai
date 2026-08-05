
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, OfficerProfile, CitizenProfile, AdminProfile
from django.db import transaction

def test_privilege_escalation_bypass():
    print("--- Security Bypass Test: User.objects.update() ---")
    # Create a normal citizen
    user = User.objects.create_user(username="test_citizen_bypass", email="bypass@test.com", password="password123", role=User.Role.CITIZEN)
    print(f"Created user: {user.username}, Role: {user.role}")

    # Attempt escalation via update()
    User.objects.filter(id=user.id).update(role=User.Role.SUPER_ADMIN)
    
    user.refresh_from_db()
    print(f"Role after update(): {user.role}")
    if user.role == User.Role.SUPER_ADMIN:
        print("ALERT: Privilege Escalation Bypass SUCCESSFUL (Vulnerability found)")
    else:
        print("Privilege Escalation Bypass BLOCKED (Safe)")

    user.delete()

def audit_role_profile_mismatch():
    print("\n--- Role/Profile Mismatch Audit ---")
    users = User.objects.all()
    mismatches = []

    for user in users:
        # Check if user has profiles they shouldn't have
        has_officer = hasattr(user, 'officer')
        has_citizen = hasattr(user, 'citizen_profile')
        has_admin = hasattr(user, 'admin_profile')

        if user.role == User.Role.CITIZEN:
            if has_officer or has_admin:
                mismatches.append((user.id, user.username, user.role, "Has Officer/Admin profile"))
        elif user.role == User.Role.OFFICER:
            if has_citizen or has_admin:
                mismatches.append((user.id, user.username, user.role, "Has Citizen/Admin profile"))
        elif user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN]:
            if has_citizen or has_officer:
                mismatches.append((user.id, user.username, user.role, "Has Citizen/Officer profile"))

    print(f"Role/Profile mismatches found: {len(mismatches)}")
    for m in mismatches[:10]:
        print(f"  - User {m[0]} ({m[1]}) Role: {m[2]} Error: {m[3]}")

if __name__ == "__main__":
    test_privilege_escalation_bypass()
    audit_role_profile_mismatch()
