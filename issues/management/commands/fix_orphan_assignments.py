from django.core.management.base import BaseCommand
from issues.models import Issue

class Command(BaseCommand):
    help = "Fix issues that are marked as ASSIGNED but have no assigned officer."

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking for orphan assigned issues...")
        
        # Detect issues where: status = "ASSIGNED" AND assigned_to IS NULL
        orphans = Issue.objects.filter(status=Issue.Status.ASSIGNED, assigned_to__isnull=True)
        count = orphans.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphan assigned issues found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {count} orphan assigned issues. Downgrading to PENDING."))
        
        for issue in orphans:
            self.stdout.write(f" Fixing Issue #CN-{issue.id}: {issue.title}")
            issue.status = Issue.Status.PENDING
            issue.save()
            
        self.stdout.write(self.style.SUCCESS(f"Successfully fixed {count} issues."))
