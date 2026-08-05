import uuid
from django.core.management.base import BaseCommand
from issues.models import Issue
from notifications.models import Notification
from accounts.models import User, Location, Department
from notifications.tasks import dispatch_notifications

class Command(BaseCommand):
    help = 'Validates Idempotency and Duplicate Protection across governance workflows.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("--- IDEMPOTENCY HARDENING DRILL ---"))
        
        citizen = User.objects.filter(role='citizen').first()
        dist = Location.objects.filter(type='district').first()
        dept = Department.objects.first()

        if not citizen or not dist:
            self.stdout.write(self.style.ERROR("Incomplete data. Seed system first."))
            return

        # 1. Test Issue Creation Idempotency
        self.stdout.write("Drill 1: Duplicate Issue Reporting...")
        ikey = f"test_issue_{uuid.uuid4()}"
        
        # First creation
        Issue.objects.create(
            title="Idempotency Test", description="Testing unique keys",
            category="Road", reported_by=citizen, location=dist, department=dept,
            idempotency_key=ikey
        )
        
        # Attempt second creation with SAME key
        try:
            Issue.objects.create(
                title="Idempotency Test DUPLICATE", description="Testing unique keys",
                category="Road", reported_by=citizen, location=dist, department=dept,
                idempotency_key=ikey
            )
            self.stdout.write(self.style.ERROR("VULNERABILITY: Duplicate issue created with same key!"))
        except Exception as e:
            self.stdout.write(self.style.SUCCESS(f"CONTAINED: DB level uniqueness blocked duplicate issue. Error: {str(e)[:50]}..."))

        # 2. Test Notification Idempotency (Task level)
        self.stdout.write("Drill 2: Duplicate Notification Dispatch...")
        
        # Dispatch first
        dispatch_notifications(citizen.id, 'issue_updated', "First notification", channels=['in_app'])
        
        # Dispatch second (identical)
        dispatch_notifications(citizen.id, 'issue_updated', "First notification", channels=['in_app'])
        
        notif_count = Notification.objects.filter(
            user=citizen, message="First notification"
        ).count()
        
        if notif_count == 1:
            self.stdout.write(self.style.SUCCESS("CONTAINED: Task-level guard blocked duplicate notification."))
        else:
            self.stdout.write(self.style.ERROR(f"VULNERABILITY: Found {notif_count} duplicate notifications!"))

        self.stdout.write(self.style.NOTICE("--- DRILL COMPLETE ---"))
