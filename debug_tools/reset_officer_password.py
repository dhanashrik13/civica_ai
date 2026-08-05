import os
import django
from django.contrib.auth import authenticate, get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

User = get_user_model()
email = "rajesh.jadhav.988@mahagov.in"
new_password = "Civica@123"

def reset_password():
    users = User.objects.filter(email__iexact=email)
    if not users.exists():
        print("USER_NOT_FOUND")
        return

    user = users.first()
    if not user.is_active:
        print("ACCOUNT_INACTIVE")
        return

    user.set_password(new_password)
    user.save()

    # Verify reset
    verified_user = authenticate(username=user.username, password=new_password)
    if verified_user:
        print("PASSWORD_RESET_SUCCESS")
    else:
        print("RESET_FAILED_VERIFICATION")

if __name__ == "__main__":
    reset_password()
