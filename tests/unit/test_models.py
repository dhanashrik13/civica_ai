import pytest
from django.core.exceptions import ValidationError
from accounts.models import User, Location, Department, OfficerProfile
from issues.models import Issue
from django.utils import timezone

@pytest.mark.django_db
class TestIssueModel:
    def setup_method(self):
        self.loc = Location.objects.create(name="Test Village", type="village")
        self.dept = Department.objects.create(name="Test Dept", level="village")
        self.citizen = User.objects.create_user(username="citizen1", email="c1@test.com", role=User.Role.CITIZEN)
        self.officer_user = User.objects.create_user(username="officer1", email="o1@test.com", role=User.Role.OFFICER)
        self.officer = OfficerProfile.objects.create(user=self.officer_user, department=self.dept, location=self.loc, level="village")

    def test_officer_cannot_report_issue(self):
        with pytest.raises(ValidationError) as exc:
            Issue.objects.create(
                title="Test", description="Test", category="pothole", priority="medium",
                reported_by=self.officer_user
            )
        assert "Officers cannot report issues." in str(exc.value)

    def test_sla_calculation(self):
        issue = Issue.objects.create(
            title="Test SLA", description="Test", category="pothole", priority="high",
            reported_by=self.citizen, sla_multiplier=1.5
        )
        # high priority base SLA = 2. Multiplier 1.5 -> 3 days
        assert issue.sla_days == 3.0

    def test_issue_auto_status_on_assignment(self):
        issue = Issue.objects.create(
            title="Test", description="Test", category="pothole", priority="medium",
            reported_by=self.citizen
        )
        assert issue.status == Issue.Status.PENDING
        
        issue.assigned_to = self.officer
        issue.save()
        assert issue.status == Issue.Status.ASSIGNED

    def test_is_overdue_logic(self):
        issue = Issue.objects.create(
            title="Overdue", description="Test", category="pothole", priority="emergency",
            reported_by=self.citizen
        )
        # Emergency SLA = 0.5 days
        assert not issue.is_overdue
        
        # Manually alter created_at using update to bypass save
        Issue.objects.filter(pk=issue.pk).update(created_at=timezone.now() - timezone.timedelta(days=1))
        issue.refresh_from_db()
        assert issue.is_overdue

@pytest.mark.django_db
class TestUserModel:
    def test_privilege_escalation_blocked(self):
        user = User.objects.create_user(username="citizen2", email="c2@test.com", role=User.Role.CITIZEN)
        
        # Attempt to escalate role via save
        user.role = User.Role.SUPER_ADMIN
        user.save()
        
        user.refresh_from_db()
        assert user.role == User.Role.CITIZEN, "Privilege escalation should be blocked"

    def test_forced_escalation_allowed(self):
        user = User.objects.create_user(username="citizen3", email="c3@test.com", role=User.Role.CITIZEN)
        user.role = User.Role.SUPER_ADMIN
        user.save(force_escalation=True)
        
        user.refresh_from_db()
        assert user.role == User.Role.SUPER_ADMIN, "Forced privilege escalation should be allowed"
