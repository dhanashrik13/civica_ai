from django.contrib.auth.hashers import make_password
from accounts.models import User

TEST_PASSWORD = "TestPassword123!"

def sync_test_users():
    roles = {
        'CITIZEN': (User.Role.CITIZEN, 'citizen_profile'),
        'OFFICER': (User.Role.OFFICER, 'officer'),
        'ADMIN': ([User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN], 'admin_profile')
    }
    
    for role_name, (role_val, profile_attr) in roles.items():
        if isinstance(role_val, list):
            users = User.objects.filter(role__in=role_val)[:5]
        else:
            users = User.objects.filter(role=role_val)[:5]
            
        print(f"\n--- SYNCING {role_name} ---")
        for user in users:
            print(f"Syncing {user.email}")
            # Set password on User model
            user.set_password(TEST_PASSWORD)
            user.save()
            
            # Sync to profile
            profile = getattr(user, profile_attr, None)
            if profile:
                profile.password_hash = make_password(TEST_PASSWORD)
                profile.save()
                print(f"Synced {user.email}")
            else:
                print(f"No profile found for {user.email}")

if __name__ == "__main__":
    sync_test_users()
