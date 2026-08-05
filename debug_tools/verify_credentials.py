import os
import django
from django.contrib.auth import authenticate, get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

User = get_user_model()
email = "rajesh.jadhav.988@mahagov.in"
password = "Gov@rajesh.jadhav.9889259"

def verify():
    users = User.objects.filter(email__iexact=email)
    if not users.exists():
        print("USER_NOT_FOUND")
        return

    user_obj = users.first()
    # authenticate usually takes username, so we find the username for this email
    user = authenticate(username=user_obj.username, password=password)
    
    if user:
        print("VALID")
    else:
        print("INVALID")

if __name__ == "__main__":
    verify()
