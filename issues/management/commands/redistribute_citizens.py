import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from issues.models import Issue

class Command(BaseCommand):
    help = "Generate realistic citizens and redistribute issues for a diverse dashboard."

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # 1. Create 20 realistic citizens
            first_names = ["Arjun", "Deepika", "Rohan", "Sonal", "Vijay", "Ananya", "Rahul", "Priya", "Amit", "Sneha", 
                           "Vikram", "Neha", "Sanjay", "Kavita", "Rajesh", "Meera", "Sunil", "Aarti", "Kishore", "Tanvi"]
            last_names = ["Sharma", "Patel", "Verma", "Iyer", "Nair", "Gupta", "Deshmukh", "Chavan", "Joshi", "Kulkarni"]
            
            created_citizens = []
            for i in range(20):
                username = f"citizen_{i+1:02d}"
                full_name = f"{random.choice(first_names)} {random.choice(last_names)}"
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "role": User.Role.CITIZEN,
                        "full_name": full_name,
                        "is_approved": True,
                        "email": f"{username}@example.com"
                    }
                )
                if created:
                    user.set_password("password123")
                    user.save()
                created_citizens.append(user)
            
            self.stdout.write(f"Created/Verified 20 citizen users.")

            # 2. Redistribute all issues
            issues = Issue.objects.all()
            count = issues.count()
            
            for issue in issues:
                issue.reported_by = random.choice(created_citizens)
                
                # Optional: Add variation in timestamps for better activity spread
                # Adjust created_at within the last 30 days
                random_days = random.randint(0, 30)
                random_hours = random.randint(0, 23)
                random_minutes = random.randint(0, 59)
                new_date = timezone.now() - timedelta(days=random_days, hours=random_hours, minutes=random_minutes)
                
                # Since auto_now_add is True, we use .update() to bypass save() if we want to change created_at
                # Or just update the instance if it's acceptable. Here we use update() for precision.
                Issue.objects.filter(id=issue.id).update(
                    reported_by=issue.reported_by,
                    created_at=new_date
                )

            self.stdout.write(self.style.SUCCESS(f"Successfully redistributed {count} issues across {len(created_citizens)} citizens."))
            
            # 3. Clean up the placeholder user if it exists and has no reports
            genuine = User.objects.filter(username="genuine_citizen").first()
            if genuine and not Issue.objects.filter(reported_by=genuine).exists():
                genuine.delete()
                self.stdout.write("Removed placeholder 'genuine_citizen' user.")
