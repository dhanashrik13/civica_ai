import os
import django
from django.contrib.auth import get_user_model
from django.urls import reverse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

User = get_user_model()
email = "rajendra.bhonsle1@mahagov.in"

def audit_account():
    print(f"Auditing Account: {email}\n")
    
    # Check 1: User Existence & Duplicates
    users = User.objects.filter(email__iexact=email)
    user_count = users.count()
    
    if user_count == 0:
        print(f"Error: No user found with email {email}")
        return
        
    user = users.first()
    
    # Table 1: Account Status
    print("TABLE 1 — ACCOUNT STATUS")
    print("| Field | Result |")
    print(f"| User ID | {user.id} |")
    print(f"| Username | {user.username} |")
    print(f"| Email (Exact) | {user.email} |")
    print(f"| Role | {user.role} |")
    print(f"| Is Active | {user.is_active} |")
    print(f"| Is Approved | {user.is_approved} |")
    print(f"| Last Login | {user.last_login} |")
    
    # Table 2: Officer Profile Status
    print("\nTABLE 2 — OFFICER PROFILE STATUS")
    print("| Validation | Result |")
    has_profile = hasattr(user, 'officer')
    print(f"| Profile Exists | {has_profile} |")
    if has_profile:
        profile = user.officer
        print(f"| Department | {profile.department.name if profile.department else 'N/A'} |")
        print(f"| Governance Level | {profile.get_level_display()} |")
        print(f"| District | {profile.district or 'N/A'} |")
        print(f"| Workload Capacity | {profile.workload_capacity} |")
        print(f"| Active Assignments | {profile.active_assigned_count} |")
    else:
        print("| Department | N/A |")
        print("| Governance Level | N/A |")

    # Table 3: Authentication Validation
    print("\nTABLE 3 — AUTHENTICATION VALIDATION")
    print("| Check | Pass/Fail |")
    print(f"| Password Usable | {'Pass' if user.has_usable_password() else 'Fail'} |")
    print(f"| Account Locked | {'Fail (Locked)' if not user.is_active else 'Pass (Active)'} |")
    
    # Email Normalization check
    normalized_email = email.lower()
    email_mismatch = user.email.lower() != normalized_email
    print(f"| Email Normalization | {'Fail (Mismatch)' if email_mismatch else 'Pass'} |")
    
    # Duplicate check
    print(f"| Single Account Entry | {'Pass' if user_count == 1 else 'Fail (Duplicate Found)'} |")
    
    # Role consistency
    role_valid = user.role == User.Role.OFFICER
    print(f"| Role Consistency | {'Pass' if role_valid else 'Fail (Wrong Role)'} |")

    # Table 4: Dashboard Access
    print("\nTABLE 4 — DASHBOARD ACCESS")
    print("| Dashboard | Access Status |")
    
    # Officer Dashboard
    try:
        officer_url = reverse("dashboards:officer_dashboard")
        # Logic check: can user reach officer dashboard?
        can_access_officer = user.role == User.Role.OFFICER
        print(f"| Officer Dashboard | {'ALLOWED' if can_access_officer else 'DENIED'} |")
    except Exception as e:
        print(f"| Officer Dashboard | ERROR: {str(e)} |")
        
    # Admin Dashboard
    can_access_admin = user.role in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]
    print(f"| Admin Dashboard | {'ALLOWED' if can_access_admin else 'DENIED'} |")
    
    # Citizen Dashboard (STRICT: SHOULD BE DENIED)
    can_access_citizen = user.role == User.Role.CITIZEN
    print(f"| Citizen Dashboard | {'ALLOWED' if can_access_citizen else 'DENIED'} |")

    # Table 5: Final Verdict
    print("\nTABLE 5 — FINAL VERDICT")
    print("| Status | Explanation |")
    
    if user.is_active and user.is_approved and role_valid and has_profile:
        print("| Healthy | Account is active, approved, and correctly linked to an Officer Profile. |")
    elif not user.is_active:
        print("| Disabled | Account is marked as inactive in the database. |")
    elif not has_profile:
        print("| Orphaned | User exists with officer role but lacks an OfficerProfile record. |")
    else:
        print("| Degraded | Account has issues that may prevent full operational use. |")

if __name__ == "__main__":
    audit_account()
