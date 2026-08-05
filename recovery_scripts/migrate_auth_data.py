import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile

def migrate_data():
    print("Starting Auth Data Migration...")
    
    # Citizens
    citizens = CitizenProfile.objects.select_related('user').all()
    citizen_count = 0
    for profile in citizens:
        if profile.user:
            profile.username = profile.user.username
            profile.email = profile.user.email
            profile.password_hash = profile.user.password
            profile.is_active = profile.user.is_active
            profile.last_login = profile.user.last_login
            profile.save(update_fields=['username', 'email', 'password_hash', 'is_active', 'last_login'])
            citizen_count += 1
    print(f"Migrated {citizen_count} Citizen profiles.")

    # Officers
    officers = OfficerProfile.objects.select_related('user').all()
    officer_count = 0
    for profile in officers:
        if profile.user:
            profile.username = profile.user.username
            profile.email = profile.user.email
            profile.password_hash = profile.user.password
            profile.is_active = profile.user.is_active
            profile.last_login = profile.user.last_login
            profile.save(update_fields=['username', 'email', 'password_hash', 'is_active', 'last_login'])
            officer_count += 1
    print(f"Migrated {officer_count} Officer profiles.")

    # Admins
    admins = AdminProfile.objects.select_related('user').all()
    admin_count = 0
    for profile in admins:
        if profile.user:
            profile.username = profile.user.username
            profile.email = profile.user.email
            profile.password_hash = profile.user.password
            profile.is_active = profile.user.is_active
            profile.last_login = profile.user.last_login
            profile.save(update_fields=['username', 'email', 'password_hash', 'is_active', 'last_login'])
            admin_count += 1
    print(f"Migrated {admin_count} Admin profiles.")

    print("\n--- VALIDATION ---")
    user_count = User.objects.count()
    print(f"Total Users: {user_count}")
    
    total_migrated = citizen_count + officer_count + admin_count
    print(f"Total Migrated Profiles: {total_migrated}")
    
    if total_migrated >= user_count:
        print("SUCCESS: All users migrated (some may have multiple profiles depending on legacy data, or it matches perfectly).")
    else:
        print(f"WARNING: Migrated {total_migrated} but there are {user_count} users. Missing some?")
        
    # Check for duplicates or missing auth data
    missing_citizens = CitizenProfile.objects.filter(username__isnull=True).count()
    missing_officers = OfficerProfile.objects.filter(username__isnull=True).count()
    missing_admins = AdminProfile.objects.filter(username__isnull=True).count()
    
    print(f"Profiles missing username: Citizens: {missing_citizens}, Officers: {missing_officers}, Admins: {missing_admins}")
    
    if missing_citizens == 0 and missing_officers == 0 and missing_admins == 0:
        print("SUCCESS: No missing auth data.")

if __name__ == '__main__':
    migrate_data()
