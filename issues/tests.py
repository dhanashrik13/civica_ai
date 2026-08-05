from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import Department, Location, OfficerProfile
from issues.forms import ReportForm
from issues.models import Issue


User = get_user_model()


def make_test_image(name="test.jpg"):
    return SimpleUploadedFile(name, b"filecontent", content_type="image/jpeg")


class IssueReportingTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            username="citizen@example.com",
            email="citizen@example.com",
            password="testpass123",
            full_name="Citizen User",
            role=User.Role.CITIZEN,
            is_active=True,
            is_approved=True,
        )
        self.officer_user = User.objects.create_user(
            username="officer@example.com",
            email="officer@example.com",
            password="testpass123",
            full_name="OfficerProfile User",
            role=User.Role.OFFICER,
            is_active=True,
            is_approved=True,
        )
        self.department = Department.objects.create(name="Road", level="village")
        self.district = Location.objects.create(name="District A", type="district")
        self.taluka = Location.objects.create(name="Taluka A", type="taluka", parent=self.district)
        self.village = Location.objects.create(name="Village A", type="village", parent=self.taluka)
        self.officer = OfficerProfile.objects.create(
            user=self.officer_user,
            department=self.department,
            location=self.village,
            village="Village A",
            taluka="Taluka A",
            district="District A",
            level="village",
        )

    def test_report_form_requires_image_and_location_fields(self):
        form = ReportForm(
            data={
                "title": "Bad road",
                "description": "A pothole has opened near the market.",
                "category": "pothole",
                "latitude": 10.0,
                "longitude": 20.0,
                "district": "District A",
                "taluka": "Taluka A",
                "village": "Village A",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("photo1", form.errors)

    def test_issue_status_becomes_assigned_when_officer_set(self):
        issue = Issue.objects.create(
            reported_by=self.citizen,
            title="Broken road near school",
            description="A dangerous pothole is getting bigger near the school gate.",
            category="pothole",
            location=self.village,
            latitude=10.0,
            longitude=20.0,
            photo1=make_test_image(),
            village="Village A",
            taluka="Taluka A",
            district="District A",
            ward="Village A",
            assigned_to=self.officer,
        )

        self.assertEqual(issue.status, Issue.Status.ASSIGNED)
        self.assertEqual(issue.created_by, self.citizen)
