from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate, get_user_model
from accounts.models import Department

User = get_user_model()

class Command(BaseCommand):
    help = 'Verifies and fixes department admin login credentials.'

    def handle(self, *args, **options):
        credentials = [
            ("admin_5@example.com", "Drainage & Sewerage Department"),
            ("admin_3@example.com", "Electricity Department"),
            ("admin_6@example.com", "General Administration"),
            ("admin_7@example.com", "Public Works Department (PWD)"),
            ("electricity_admin@example.com", "Electricity Department"),
            ("road_admin@example.com", "Public Works Department (PWD)"),
            ("sanitation_admin@example.com", "Sanitation Department"),
            ("water_admin@example.com", "Water Supply Department"),
        ]
        
        password = "Admin@123"
        
        self.stdout.write("-" * 85)
        self.stdout.write(f"{'Email':<35} | {'Exists':<8} | {'Login Status':<15} | {'Issue/Action'}")
        self.stdout.write("-" * 85)

        for email, dept_name in credentials:
            user = User.objects.filter(email=email).first()
            exists = "Yes" if user else "No"
            status = "Failed"
            issue = ""

            if not user:
                # Task 4: Create missing user
                dept = Department.objects.filter(name__iexact=dept_name).first()
                if not dept:
                    issue = f"Dept '{dept_name}' not found"
                else:
                    username = email.split('@')[0]
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        role=User.Role.DEPT_ADMIN,
                        department=dept,
                        is_staff=True,
                        is_active=True,
                        is_approved=True
                    )
                    issue = "Created missing user"
                    exists = "Fixed"

            if user:
                # Task 1 & 5: Verify and Fix
                if not user.is_active:
                    user.is_active = True
                    user.save()
                    issue += " Activated user;"
                
                if not user.is_approved:
                    user.is_approved = True
                    user.save()
                    issue += " Approved user;"
                
                if user.role != User.Role.DEPT_ADMIN:
                    user.role = User.Role.DEPT_ADMIN
                    user.save()
                    issue += " Updated role;"

                # Test Auth
                auth_user = authenticate(username=user.username, password=password)
                if auth_user:
                    status = "Success"
                else:
                    # Reset password if auth fails
                    user.set_password(password)
                    user.save()
                    auth_user = authenticate(username=user.username, password=password)
                    if auth_user:
                        status = "Fixed"
                        issue += " Reset password;"
                    else:
                        status = "Failed"
                        issue += " Auth logic error;"

            self.stdout.write(f"{email:<35} | {exists:<8} | {status:<15} | {issue or 'None'}")

        self.stdout.write("-" * 85)
