from django.core.management.base import BaseCommand
from issues.models import Issue
from accounts.models import OfficerProfile, User
import random
from django.db import transaction

class Command(BaseCommand):
    help = "Create 10 test issues for same location and assign to drainage_27"

    def handle(self, *args, **kwargs):
        try:
            # Get the officer user
            officer_user = User.objects.get(email="drainage_27@civicpulse.com")
            officer = OfficerProfile.objects.get(user=officer_user)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR("OfficerProfile drainage_27@civicpulse.com not found"))
            return
        except OfficerProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR("OfficerProfile profile for drainage_27 not found"))
            return

        department = officer.department
        location = officer.location
        
        # We need a citizen to report the issue to pass validation in Issue.save()
        reporter = User.objects.filter(role=User.Role.CITIZEN).first()
        if not reporter:
            # Create a test citizen if none exists
            reporter = User.objects.create_user(
                username="test_citizen_reporter",
                email="test_citizen@example.com",
                password="password123",
                role=User.Role.CITIZEN,
                is_approved=True
            )
            
        self.stdout.write(f"Using reporter: {reporter.email}")
        self.stdout.write(f"Assigning to officer: {officer_user.email} in location: {location.name if location else 'N/A'}")

        created_count = 0
        with transaction.atomic():
            for i in range(10):
                Issue.objects.create(
                    title=f"Test Drainage Issue {i+1}",
                    description="Auto-generated test issue for specific officer assignment and location testing.",
                    category=Issue.Category.DRAINAGE,
                    department=department,
                    location=location,
                    priority=random.choice([Issue.Priority.LOW, Issue.Priority.MEDIUM, Issue.Priority.HIGH]),
                    status=Issue.Status.ASSIGNED,
                    assigned_to=officer,
                    reported_by=reporter,
                    # Sync location details from officer
                    village=officer.village,
                    taluka=officer.taluka,
                    district=officer.district,
                    latitude=random.uniform(18.4, 18.6),
                    longitude=random.uniform(73.7, 73.9),
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully created {created_count} issues and assigned to {officer_user.email}"))
