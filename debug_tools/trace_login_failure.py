import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.services import authenticate_for_role

email = "rajesh.jadhav.988@mahagov.in"
password = "NewStrongPassword123!"

def trace_login():
    print(f"Tracing login for {email} with role 'officer'...")
    profile = authenticate_for_role(None, email, password, 'officer')
    if profile:
        print("LOGIN_TRACE_SUCCESS: authenticate_for_role returned profile")
    else:
        print("LOGIN_TRACE_FAILURE: authenticate_for_role returned None")
        
        # Check why
        from accounts.models import OfficerProfile
        off = OfficerProfile.objects.filter(email=email.lower().strip(), is_active=True).first()
        if not off:
            print("REASON: OfficerProfile not found or inactive")
        else:
            from django.contrib.auth.hashers import check_password
            if not check_password(password, off.password_hash):
                print("REASON: Password mismatch in OfficerProfile.password_hash")
            else:
                print("REASON: Unknown (password matched but profile still not returned?)")

if __name__ == "__main__":
    trace_login()
