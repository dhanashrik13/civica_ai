from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Department

User = get_user_model()

class Command(BaseCommand):
    help = "Seed RBAC data: Departments, Super Admin, and Department Admins"

    def handle(self, *args, **options):
        # 1. Create Departments
        dept_names = ["Road", "Water", "Electricity", "Sanitation"]
        depts = {}
        for name in dept_names:
            dept, created = Department.objects.get_or_create(name=name)
            depts[name] = dept
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Department: {name}"))
            else:
                self.stdout.write(f"Department already exists: {name}")

        # 2. Create Super Admin
        if not User.objects.filter(username="superadmin").exists():
            User.objects.create_superuser(
                username="superadmin",
                email="superadmin@example.com",
                password="Admin@123",
                role=User.Role.SUPER_ADMIN,
                full_name="Super Admin"
            )
            self.stdout.write(self.style.SUCCESS("Created Super Admin: superadmin / Admin@123"))
        else:
            self.stdout.write("Super Admin 'superadmin' already exists.")

        # 3. Create Department Admins
        dept_admin_data = [
            ("road_admin", "Road"),
            ("water_admin", "Water"),
            ("electricity_admin", "Electricity"),
            ("sanitation_admin", "Sanitation"),
        ]

        for username, dept_name in dept_admin_data:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                    password="Admin@123",
                    role=User.Role.DEPT_ADMIN,
                    department=depts[dept_name],
                    full_name=f"{dept_name} Admin",
                    is_approved=True
                )
                self.stdout.write(self.style.SUCCESS(f"Created Dept Admin: {username} / Admin@123 -> {dept_name}"))
            else:
                self.stdout.write(f"Dept Admin '{username}' already exists.")

        self.stdout.write(self.style.SUCCESS("RBAC Seeding completed successfully."))
