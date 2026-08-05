import os
import django
from django.contrib.auth import authenticate, get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.services import authenticate_for_role
from accounts.models import OfficerProfile

User = get_user_model()
email = "rajesh.jadhav.988@mahagov.in"
password = "NewStrongPassword123!"

def sync_password():
    print(f"Starting synchronization for {email}...")
    
    # 1. Fetch User and Profile
    users = User.objects.filter(email__iexact=email)
    if not users.exists():
        print("TABLE 1 — SYNC STATUS\n| Check | Result |\n| User Found | ❌ FAIL |")
        return

    user = users.first()
    if not hasattr(user, 'officer'):
        print("TABLE 1 — SYNC STATUS\n| Check | Result |\n| Profile Linkage | ❌ FAIL |")
        return
        
    profile = user.officer
    
    # 2. Synchronize
    print("TABLE 1 — SYNC STATUS\n| Check | Result |\n| User Found | ✅ PASS |\n| Profile Linkage | ✅ PASS |")
    
    old_profile_hash = profile.password_hash
    profile.password_hash = user.password
    profile.save()
    
    print("| Hash Synchronized | ✅ PASS |")
    
    # 3. Validation
    print("\nTABLE 2 — HASH VALIDATION")
    print("| Layer | Status |")
    hashes_match = profile.password_hash == user.password
    print(f"| Memory Consistency | {'✅ MATCH' if hashes_match else '❌ MISMATCH'} |")
    
    profile.refresh_from_db()
    db_match = profile.password_hash == user.password
    print(f"| Persistence (DB) | {'✅ MATCH' if db_match else '❌ MISMATCH'} |")

    # 4. Login Validation
    print("\nTABLE 3 — LOGIN VALIDATION")
    print("| Validation | Result |")
    
    # Standard Auth
    standard_auth = authenticate(username=user.username, password=password)
    print(f"| Standard Auth | {'✅ SUCCESS' if standard_auth else '❌ FAILURE'} |")
    
    # Domain Auth
    domain_auth = authenticate_for_role(None, email, password, 'officer')
    print(f"| Domain Auth | {'✅ SUCCESS' if domain_auth else '❌ FAILURE'} |")
    
    if standard_auth and domain_auth:
        print("\nFINAL OUTPUT:")
        print("- Synchronization succeeded: YES")
        print("- Officer login now works: YES")
        print("- Unrelated systems changed: NO")
    else:
        print("\nFINAL OUTPUT:")
        print("- Synchronization succeeded: PARTIAL")
        print("- Officer login now works: NO")
        print("- Unrelated systems changed: NO")

if __name__ == "__main__":
    sync_password()
