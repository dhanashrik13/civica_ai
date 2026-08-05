
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, OfficerProfile

def test_full_name_mismatch():
    print("--- Property Setter/Getter Consistency Test ---")
    # Create an officer with a profile
    user = User.objects.create_user(username="test_consistency", email="const@test.com", password="password123", role=User.Role.OFFICER)
    # create_officer_account might be better but let's do it manually for speed
    from accounts.models import Department, Location
    dept = Department.objects.first()
    loc = Location.objects.first()
    profile = OfficerProfile.objects.create(user=user, department=dept, location=loc, full_name="Original Name")
    
    user.refresh_from_db()
    print(f"Current full_name (getter): {user.full_name}")
    
    # Attempt to update via property
    user.full_name = "Updated Name"
    user.save()
    
    user.refresh_from_db()
    print(f"Full name after update (getter): {user.full_name}")
    print(f"Legacy full_name field: {user._legacy_full_name}")
    print(f"OfficerProfile full_name field: {user.officer.full_name}")
    
    if user.full_name == "Updated Name":
        print("SUCCESS: Property update reflected (Safe)")
    else:
        print("FAILURE: Property update NOT reflected in getter (Inconsistent)")

    user.delete()

if __name__ == "__main__":
    test_full_name_mismatch()
