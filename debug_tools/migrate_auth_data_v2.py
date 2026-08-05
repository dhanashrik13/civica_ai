import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from django.db import transaction

def migrate_data():
    print("Starting Auth Data Migration...")
    
    with transaction.atomic():
        # CitizenProfiles
        citizens = CitizenProfile.objects.select_related('user').all()
        print(f"Migrating {citizens.count()} CitizenProfiles...")
        for profile in citizens:
            user = profile.user
            profile.username = user.username
            profile.email = user.email
            profile.password_hash = user.password
            profile.is_active = user.is_active
            profile.last_login = user.last_login
            # We don't strictly need to overwrite created_at if it's already set by auto_now_add,
            # but for consistency with User.date_joined:
            profile.created_at = user.date_joined
            profile.save()

        # OfficerProfiles
        officers = OfficerProfile.objects.select_related('user').all()
        print(f"Migrating {officers.count()} OfficerProfiles...")
        for profile in officers:
            user = profile.user
            profile.username = user.username
            profile.email = user.email
            profile.password_hash = user.password
            profile.is_active = user.is_active
            profile.last_login = user.last_login
            profile.created_at = user.date_joined
            profile.save()

        # AdminProfiles
        admins = AdminProfile.objects.select_related('user').all()
        print(f"Migrating {admins.count()} AdminProfiles...")
        for profile in admins:
            user = profile.user
            profile.username = user.username
            profile.email = user.email
            profile.password_hash = user.password
            profile.is_active = user.is_active
            profile.last_login = user.last_login
            profile.created_at = user.date_joined
            profile.save()

    print("Auth Data Migration Completed Successfully.")

if __name__ == "__main__":
    migrate_data()
