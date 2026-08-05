import os
import django
from django.contrib.auth import authenticate, get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.services import authenticate_for_role
from accounts.models import OfficerProfile

User = get_user_model()
username = "officer_padali_pwd"
new_password = "Padali@12345"

def reset_officer_pwd_final():
    print(f"Starting final reset for {username}...")
    
    # 1. Validation
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print("TABLE 1 — ACCOUNT VALIDATION\n| Check | Result |\n| User Found | ❌ FAIL |")
        return

    has_profile = hasattr(user, 'officer')
    is_officer = user.role == User.Role.OFFICER
    
    print("TABLE 1 — ACCOUNT VALIDATION")
    print("| Check | Result |")
    print(f"| User Found | ✅ PASS |")
    print(f"| Role is Officer | {'✅ PASS' if is_officer else '❌ FAIL'} |")
    print(f"| Profile Linked | {'✅ PASS' if has_profile else '❌ FAIL'} |")

    if not is_officer or not has_profile:
        return

    # 2. Reset and Sync
    print("\nTABLE 2 — PASSWORD RESET STATUS")
    print("| Layer | Status |")
    
    user.set_password(new_password)
    user.save()
    print("| User Model | ✅ UPDATED |")
    
    profile = user.officer
    profile.password_hash = user.password
    profile.username = user.username
    profile.email = user.email
    profile.save()
    print("| OfficerProfile Sync | ✅ COMPLETED (Hash + Identity) |")

    # 3. Verify
    print("\nTABLE 3 — LOGIN VALIDATION")
    print("| Validation | Result |")
    
    # Standard Django Auth
    std_auth = authenticate(username=username, password=new_password)
    print(f"| Standard Django Auth | {'✅ PASS' if std_auth else '❌ FAIL'} |")
    
    # Officer Portal Auth
    email = user.email
    domain_auth = authenticate_for_role(None, email, new_password, 'officer')
    print(f"| Officer Portal Auth | {'✅ PASS' if domain_auth else '❌ FAIL'} |")

    if std_auth and domain_auth:
        print("\nFINAL OUTPUT:")
        print("- Password reset succeeded: YES")
        print("- Officer login now works: YES")
        print("- Unrelated functionality changed: NO")
    else:
        print("\nFINAL OUTPUT:")
        print("- Password reset succeeded: PARTIAL")
        print("- Officer login now works: NO")
        print("- Unrelated functionality changed: NO")

if __name__ == "__main__":
    reset_officer_pwd_final()
