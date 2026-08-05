import random
import requests
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from issues.models import Issue
from accounts.models import Location, IssueImage
from issues.services import map_category_to_department
from dashboards.services import auto_assign_issue

User = get_user_model()

class Command(BaseCommand):
    help = "Generate 50 drainage issues with images using existing logic."

    def handle(self, *args, **kwargs):
        citizens = User.objects.filter(role=User.Role.CITIZEN)
        if not citizens.exists():
            self.stdout.write(self.style.ERROR("No citizens found in DB. Run seed command first."))
            return

        locations = Location.objects.all()
        if not locations.exists():
            self.stdout.write(self.style.ERROR("No locations found in DB."))
            return

        sample_titles = [
            "Blocked drain in residential area",
            "Sewage overflow on main road",
            "Broken drainage pipe leakage",
            "Open drainage hazards",
            "Clogged pipeline after rain"
        ]

        image_url = "https://picsum.photos/400/300"
        created_count = 0

        self.stdout.write(f"Generating 50 drainage issues and auto-assigning...")

        for i in range(50):
            citizen = random.choice(citizens)
            location_obj = random.choice(locations)
            title = random.choice(sample_titles)
            
            issue = Issue.objects.create(
                title=f"{title} #gen_{i+1}",
                description=f"{title} reported at {location_obj.name}. Immediate attention required for public health.",
                category=Issue.Category.DRAINAGE,
                location=location_obj.name,
                district=location_obj.name if location_obj.type == "district" else "Pune",
                reported_by=citizen,
                status=Issue.Status.PENDING,
                latitude=random.uniform(18.4, 18.6),
                longitude=random.uniform(73.7, 73.9),
            )
            
            # 1. Assign Department (CRITICAL for assignment logic)
            issue.department = map_category_to_department(issue.category)
            issue.save()

            # 2. Trigger Auto Assignment logic
            auto_assigned = auto_assign_issue(issue)

            # Attach image via IssueImage model as requested
            try:
                img_response = requests.get(image_url, timeout=10)
                if img_response.status_code == 200:
                    image_file = ContentFile(img_response.content, name=f"drainage_{issue.id}.jpg")
                    IssueImage.objects.create(
                        issue=issue,
                        image=image_file
                    )
                    # Also populate photo1 for dashboard compatibility if used
                    issue.photo1.save(f"drainage_p1_{issue.id}.jpg", ContentFile(img_response.content), save=True)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Failed to fetch image for issue {issue.id}: {e}"))

            created_count += 1
            if created_count % 10 == 0:
                self.stdout.write(f"Created {created_count} issues (Auto-assigned: {auto_assigned})...")

        self.stdout.write(self.style.SUCCESS(f"Successfully created 50 drainage issues with images and triggered assignment."))
