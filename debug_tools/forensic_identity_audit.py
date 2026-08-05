import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from django.core.exceptions import ObjectDoesNotExist

def audit_identity_integrity():
    print("=== IDENTITY DOMAIN INTEGRITY AUDIT ===")
    users = User.objects.all()
    total_users = users.count()
    print(f"Total Users: {total_users}")

    issues = []

    for user in users:
        has_citizen = hasattr(user, 'citizen_profile')
        has_officer = hasattr(user, 'officer')
        has_admin = hasattr(user, 'admin_profile')

        profiles_count = sum([has_citizen, has_officer, has_admin])

        # 1. Multiple Profiles Check
        if profiles_count > 1:
            profiles_found = []
            if has_citizen: profiles_found.append("Citizen")
            if has_officer: profiles_found.append("Officer")
            if has_admin: profiles_found.append("Admin")
            issues.append({
                'username': user.username,
                'role': user.role,
                'issue': f"MULTIPLE_PROFILES: {', '.join(profiles_found)}",
                'severity': 'CRITICAL'
            })

        # 2. Role/Profile Mismatch & Missing Profiles
        if user.role == User.Role.CITIZEN:
            if not has_citizen:
                issues.append({'username': user.username, 'role': user.role, 'issue': "MISSING_CITIZEN_PROFILE", 'severity': 'HIGH'})
            if has_officer:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_OFFICER_PROFILE", 'severity': 'CRITICAL'})
            if has_admin:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_ADMIN_PROFILE", 'severity': 'CRITICAL'})

        elif user.role == User.Role.OFFICER:
            if not has_officer:
                issues.append({'username': user.username, 'role': user.role, 'issue': "MISSING_OFFICER_PROFILE", 'severity': 'HIGH'})
            if has_citizen:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_CITIZEN_PROFILE", 'severity': 'CRITICAL'})
            if has_admin:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_ADMIN_PROFILE", 'severity': 'CRITICAL'})

        elif user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN]:
            if not has_admin:
                issues.append({'username': user.username, 'role': user.role, 'issue': "MISSING_ADMIN_PROFILE", 'severity': 'HIGH'})
            if has_citizen:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_CITIZEN_PROFILE", 'severity': 'CRITICAL'})
            if has_officer:
                issues.append({'username': user.username, 'role': user.role, 'issue': "ILLEGAL_OFFICER_PROFILE", 'severity': 'CRITICAL'})

    # 3. Orphan Profiles
    citizen_orphans = CitizenProfile.objects.filter(user__isnull=True).count()
    officer_orphans = OfficerProfile.objects.filter(user__isnull=True).count()
    admin_orphans = AdminProfile.objects.filter(user__isnull=True).count()

    if citizen_orphans > 0:
        issues.append({'username': 'N/A', 'role': 'N/A', 'issue': f"ORPHAN_CITIZEN_PROFILES: {citizen_orphans}", 'severity': 'MEDIUM'})
    if officer_orphans > 0:
        issues.append({'username': 'N/A', 'role': 'N/A', 'issue': f"ORPHAN_OFFICER_PROFILES: {officer_orphans}", 'severity': 'MEDIUM'})
    if admin_orphans > 0:
        issues.append({'username': 'N/A', 'role': 'N/A', 'issue': f"ORPHAN_ADMIN_PROFILES: {admin_orphans}", 'severity': 'MEDIUM'})

    # Summary
    print(f"Total Issues Detected: {len(issues)}")
    if issues:
        print("\n--- DETAILED ISSUES ---")
        for issue in issues:
            print(f"[{issue['severity']}] User: {issue['username']} (Role: {issue['role']}) - Issue: {issue['issue']}")
    else:
        print("\nAll Clear: Identity Domain Separation verified.")

    # Classification
    if any(i['severity'] == 'CRITICAL' for i in issues):
        print("\nVERDICT: DOMAIN LEAKAGE DETECTED")
    elif any(i['severity'] == 'HIGH' for i in issues):
        print("\nVERDICT: PARTIALLY CORRUPTED")
    elif issues:
        print("\nVERDICT: MINOR INCONSISTENCIES")
    else:
        print("\nVERDICT: SAFE")

if __name__ == "__main__":
    audit_identity_integrity()
