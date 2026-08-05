from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from accounts.models import User
from issues.models import Issue

class Command(BaseCommand):
    help = "Cleanup users with incorrect roles and reassign issues to valid citizens."

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # 1. Identify users who are NOT citizens but have citizen role
            mismatched_users = User.objects.filter(role=User.Role.CITIZEN).filter(
                Q(username__icontains='officer') | 
                Q(username__icontains='admin') | 
                Q(username__icontains='sanitation') | 
                Q(username__icontains='road') | 
                Q(username__icontains='water') | 
                Q(username__icontains='electric') | 
                Q(username__icontains='drainage')
            )
            
            mismatched_ids = list(mismatched_users.values_list('id', flat=True))
            mismatched_count = mismatched_users.count()
            self.stdout.write(f"Found {mismatched_count} users with role/username mismatch.")

            # 2. Get or create a valid default citizen for reassignment
            valid_citizen, created = User.objects.get_or_create(
                username="genuine_citizen",
                defaults={
                    "role": User.Role.CITIZEN,
                    "full_name": "Genuine Citizen",
                    "is_approved": True
                }
            )
            if created:
                valid_citizen.set_password("password123")
                valid_citizen.save()
            
            # 3. Reassign issues reported by these mismatched users
            affected_issues = Issue.objects.filter(reported_by_id__in=mismatched_ids)
            reassigned_count = affected_issues.count()
            affected_issues.update(reported_by=valid_citizen)
            self.stdout.write(f"Reassigned {reassigned_count} issues to 'genuine_citizen'.")

            # 4. Correct the roles of these users
            # Most of these seem to be officers based on usernames
            # We'll set them to OFFICER role if they have department-like names
            officer_keywords = ['officer', 'sanitation', 'road', 'water', 'electric', 'drainage']
            
            updated_roles = 0
            for user in mismatched_users:
                if any(kw in user.username.lower() for kw in officer_keywords):
                    user.role = User.Role.OFFICER
                elif 'admin' in user.username.lower():
                    user.role = User.Role.DEPT_ADMIN
                user.save()
                updated_roles += 1
            
            self.stdout.write(f"Updated roles for {updated_roles} users.")
            self.stdout.write(self.style.SUCCESS("Cleanup complete."))
