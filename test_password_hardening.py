import os
import django
import sys
from django.contrib.auth.hashers import check_password

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import CitizenProfile
from accounts.forms import CitizenPasswordChangeForm

def test_password_hardening():
    print("--- PASSWORD MANAGEMENT HARDENING VALIDATION ---")
    
    # Get a test citizen
    profile = CitizenProfile.objects.first()
    if not profile:
        print("No CitizenProfile found for testing.")
        return

    old_hash = profile.password_hash
    print(f"Initial Password Hash: {old_hash[:30]}...")

    # Simulate Admin Password Change
    new_pw = "Hardened@2026"
    form_data = {
        'username': profile.username,
        'email': profile.email,
        'new_password': new_pw,
        'confirm_password': new_pw,
        'is_active': profile.is_active,
        # Other required model fields might be needed if they don't have defaults
        'first_name': profile.first_name,
        'last_name': profile.last_name,
        'gender': profile.gender,
        'district': profile.district,
        'city': profile.city,
    }
    
    form = CitizenPasswordChangeForm(data=form_data, instance=profile)
    if form.is_valid():
        form.save()
        profile.refresh_from_db()
        new_hash = profile.password_hash
        print(f"Updated Password Hash: {new_hash[:30]}...")
        
        # Verify Hashing
        if new_hash != old_hash:
            print("SUCCESS: Password hash updated.")
        else:
            print("FAILURE: Password hash DID NOT update.")

        # Verify algorithm
        if new_hash.startswith('pbkdf2_sha256$'):
            print("SUCCESS: Using pbkdf2_sha256 algorithm.")
        else:
            print(f"FAILURE: Unexpected algorithm: {new_hash.split('$')[0]}")

        # Verify login (check_password)
        if check_password(new_pw, new_hash):
            print("SUCCESS: New password verified with check_password.")
        else:
            print("FAILURE: New password could not be verified.")
            
        # Verify Sync to User
        if check_password(new_pw, profile.user.password):
            print("SUCCESS: Password synced to User model.")
        else:
            print("FAILURE: Password NOT synced to User model.")

        # Restore (optional, but good for idempotency if needed)
        # profile.password_hash = old_hash
        # profile.user.password = old_hash
        # profile.save()
        # profile.user.save()
        
    else:
        print(f"Form Errors: {form.errors}")

if __name__ == "__main__":
    test_password_hardening()
