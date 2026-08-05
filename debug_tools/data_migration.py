import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from django.db import transaction

def main():
    print("Starting Safe Data Migration...")
    users = User.objects.all()
    count = 0
    with transaction.atomic():
        for user in users:
            if user.role == User.Role.CITIZEN:
                profile, _ = CitizenProfile.objects.get_or_create(user=user)
                # Only copy if empty
                if not profile.full_name: profile.full_name = user._legacy_full_name or ''
                if not profile.phone: profile.phone = user._legacy_phone_no or ''
                if not profile.address: profile.address = user._legacy_address or ''
                profile.save()
            elif user.role == User.Role.OFFICER:
                if hasattr(user, 'officer'):
                    profile = user.officer
                    if not profile.full_name: profile.full_name = user._legacy_full_name or ''
                    if not profile.phone: profile.phone = user._legacy_phone_no or ''
                    if not profile.address: profile.address = user._legacy_address or ''
                    if not profile.city: profile.city = user._legacy_city or ''
                    profile.save()
            elif user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN]:
                profile, _ = AdminProfile.objects.get_or_create(user=user)
                if not profile.full_name: profile.full_name = user._legacy_full_name or ''
                if not profile.phone_no: profile.phone_no = user._legacy_phone_no or ''
                if not profile.department_id and user._legacy_department_id:
                    profile.department_id = user._legacy_department_id
                profile.save()
            count += 1
            if count % 100 == 0:
                print(f"Processed {count} users...")
    print(f"Successfully migrated data for {count} users.")

if __name__ == "__main__":
    main()