import pytest
from django.core.exceptions import PermissionDenied
from accounts.models import User, Location, Department, OfficerProfile
from issues.models import Issue
from issues.services import secure_issue_assignment, administrative_emergency_override

@pytest.mark.django_db
class TestJurisdictionAndRBAC:
    def setup_method(self):
        self.loc_a = Location.objects.create(name="Village A", type="village")
        self.loc_b = Location.objects.create(name="Village B", type="village")
        
        self.dept_road = Department.objects.create(name="Roads", level="village")
        self.dept_water = Department.objects.create(name="Water", level="village")

        self.citizen = User.objects.create_user(username="cit", email="c@test.com", role=User.Role.CITIZEN)
        
        self.admin_user = User.objects.create_user(username="admin_road", email="ar@test.com", role=User.Role.DEPT_ADMIN)
        self.admin_user.department = self.dept_road
        self.admin_user.save(force_escalation=True)

        self.officer_user_a = User.objects.create_user(username="off_a", email="oa@test.com", role=User.Role.OFFICER)
        self.officer_a = OfficerProfile.objects.create(user=self.officer_user_a, department=self.dept_road, location=self.loc_a, level="village")

        self.officer_user_b = User.objects.create_user(username="off_b", email="ob@test.com", role=User.Role.OFFICER)
        self.officer_b = OfficerProfile.objects.create(user=self.officer_user_b, department=self.dept_water, location=self.loc_b, level="village")

        self.issue_a = Issue.objects.create(
            title="Pothole", description="Bad road", category="pothole", priority="medium",
            reported_by=self.citizen, department=self.dept_road, location=self.loc_a
        )

    def test_cross_department_assignment_blocked(self):
        # Admin for Roads tries to assign to Water officer
        with pytest.raises(PermissionDenied) as exc:
            secure_issue_assignment(self.issue_a, self.officer_b, self.admin_user)
        assert "Cannot assign to officer in another department" in str(exc.value)

    def test_cross_location_assignment_blocked(self):
        # Move OfficerProfile A to a different location, try assigning Issue A to them
        self.officer_a.location = self.loc_b
        self.officer_a.save()
        with pytest.raises(PermissionDenied) as exc:
            secure_issue_assignment(self.issue_a, self.officer_a, self.admin_user)
        assert "does not match issue location" in str(exc.value)

    def test_administrative_emergency_override(self):
        super_admin = User.objects.create_user(username="super", email="sa@test.com", role=User.Role.SUPER_ADMIN)
        
        # Override jurisdiction
        updated_issue = administrative_emergency_override(self.issue_a, self.officer_b, super_admin)
        assert updated_issue.assigned_to == self.officer_b
        assert updated_issue.status == Issue.Status.ASSIGNED
        assert updated_issue.priority == "emergency"
        assert "EMERGENCY OVERRIDE" in updated_issue.assignment_explanation

    def test_admin_override_by_non_admin_fails(self):
        with pytest.raises(PermissionDenied) as exc:
            administrative_emergency_override(self.issue_a, self.officer_a, self.officer_user_a)
        assert "Only Administrators can perform emergency overrides" in str(exc.value)
