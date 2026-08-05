import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, OfficerProfile, Department, Location
from issues.models import Issue

class Command(BaseCommand):
    help = "Seed the database with sample issues for testing the dashboard."

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding data...")

        # 1. Get or create departments
        depts = list(Department.objects.all())
        if not depts:
            depts = [
                Department.objects.create(name="Roads & Transport", level="district"),
                Department.objects.create(name="Water Supply", level="taluka"),
                Department.objects.create(name="Sanitation", level="village"),
                Department.objects.create(name="Electricity", level="district"),
            ]

        # 2. Get or create users/officers
        citizens = list(User.objects.filter(role=User.Role.CITIZEN))
        if not citizens:
            for i in range(5):
                citizens.append(User.objects.create_user(
                    username=f"citizen{i}",
                    email=f"citizen{i}@example.com",
                    password="password123",
                    full_name=f"Citizen {i}",
                    role=User.Role.CITIZEN
                ))

        officers = list(OfficerProfile.objects.all())
        if not officers:
            # Need locations for officers
            loc, _ = Location.objects.get_or_create(name="Default City", type="district")
            for i in range(3):
                u = User.objects.create_user(
                    username=f"officer{i}",
                    email=f"officer{i}@example.com",
                    password="password123",
                    full_name=f"OfficerProfile {i}",
                    role=User.Role.OFFICER
                )
                officers.append(OfficerProfile.objects.create(
                    user=u,
                    department=random.choice(depts),
                    location=loc,
                    level="district"
                ))

        # 3. Create issues
        categories = [c[0] for c in Issue.Category.choices]
        priorities = [p[0] for p in Issue.Priority.choices]
        statuses = [s[0] for s in Issue.Status.choices]

        # Locations (around Pune/Mumbai area for demo)
        locations = [
            (18.5204, 73.8567, "Pune City"),
            (19.0760, 72.8777, "Mumbai Center"),
            (18.9220, 72.8347, "Gateway of India"),
            (18.5590, 73.7913, "Baner, Pune"),
            (18.5089, 73.9259, "Hadapsar, Pune"),
        ]

        now = timezone.now()

        for i in range(50):
            created_at = now - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23))
            status = random.choice(statuses)
            resolved_at = None
            if status == Issue.Status.RESOLVED:
                resolved_at = created_at + timedelta(days=random.randint(1, 5))
                if resolved_at > now: resolved_at = now

            lat, lng, loc_name = random.choice(locations)
            # Add some jitter
            lat += random.uniform(-0.05, 0.05)
            lng += random.uniform(-0.05, 0.05)

            Issue.objects.create(
                title=f"Sample Issue {i}: {random.choice(categories).replace('_', ' ').title()}",
                description=f"Automated description for sample issue {i}.",
                category=random.choice(categories),
                priority=random.choice(priorities),
                department=random.choice(depts),
                location=loc_name,
                latitude=lat,
                longitude=lng,
                status=status,
                reported_by=random.choice(citizens),
                assigned_to=random.choice(officers) if status != Issue.Status.PENDING else None,
                created_at=created_at,
                resolved_at=resolved_at
            )
            # We need to manually set created_at because auto_now_add=True
            Issue.objects.filter(title=f"Sample Issue {i}: {random.choice(categories).replace('_', ' ').title()}").update(created_at=created_at)

        # Fix: Need to fetch the issues again because we need to update created_at properly
        # Actually update() works fine on queryset.

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded 50 issues."))
