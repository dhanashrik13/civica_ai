import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Department

class Command(BaseCommand):
    help = 'Ensures each department has exactly one Department Admin user.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Department Admin sync..."))
        self.stdout.write("-" * 60)
        self.stdout.write(f"{'Department Name':<25} | {'Email':<30} | {'Password'}")
        self.stdout.write("-" * 60)

        default_password = "Admin@123"
        departments = Department.objects.all()

        if not departments.exists():
            self.stdout.write(self.style.WARNING("No departments found in the database."))
            return

        for dept in departments:
            # Check if an admin already exists for this department
            admin_user = User.objects.filter(
                role=User.Role.DEPT_ADMIN,
                department=dept
            ).first()

            created = False
            if not admin_user:
                username = f"admin_{dept.id}"
                email = f"admin_{dept.id}@example.com"
                
                # Ensure username/email uniqueness globally
                if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                    # If conflict exists but not linked to this dept, skip or handle
                    self.stdout.write(self.style.ERROR(f"Conflict: User with username/email for Dept {dept.id} already exists but is not a Dept Admin for this dept."))
                    continue

                with transaction.atomic():
                    admin_user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=default_password,
                        role=User.Role.DEPT_ADMIN,
                        department=dept,
                        full_name=f"{dept.name} Admin",
                        is_staff=True,
                        is_active=True,
                        is_approved=True
                    )
                    created = True

            status_style = self.style.SUCCESS if created else self.style.NOTICE
            self.stdout.write(f"{dept.name[:25]:<25} | {admin_user.email:<30} | {default_password if created else '[EXISTING]'}")

        self.stdout.write("-" * 60)
        self.stdout.write(self.style.SUCCESS("Department Admin sync complete."))
