from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Department, Location, OfficerProfile, User
from issues.models import Issue
from django.core.exceptions import ValidationError

User = get_user_model()

class RBACJurisdictionTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Road", level="village")
        
        # Pune District
        self.pune = Location.objects.create(name="Pune", type="district")
        self.pune_taluka = Location.objects.create(name="Haveli", type="taluka", parent=self.pune)
        self.pune_village = Location.objects.create(name="Wagholi", type="village", parent=self.pune_taluka)
        
        # Nagpur District
        self.nagpur = Location.objects.create(name="Nagpur", type="district")
        self.nagpur_taluka = Location.objects.create(name="N-Taluka", type="taluka", parent=self.nagpur)
        self.nagpur_village = Location.objects.create(name="N-Village", type="village", parent=self.nagpur_taluka)
        
        # Pune OfficerProfile
        self.pune_off_user = User.objects.create_user(username="pune_off", email="off@pune.com", role="officer")
        self.pune_officer = OfficerProfile.objects.create(
            user=self.pune_off_user, department=self.dept, location=self.pune_village, level="village"
        )
        
        # Citizen
        self.citizen = User.objects.create_user(username="citizen", email="cit@pune.com", role="citizen")

    def test_block_cross_location_assignment(self):
        # Create issue in Nagpur
        issue = Issue.objects.create(
            reported_by=self.citizen,
            title="Broken road in Nagpur",
            category="road_damage",
            location=self.nagpur_village,
            photo1="test.jpg"
        )
        
        # Try to assign Pune officer to Nagpur issue
        issue.assigned_to = self.pune_officer
        
        # Should raise ValidationError in save()
        with self.assertRaises(ValidationError) as cm:
            issue.save()
        
        self.assertIn("OfficerProfile location must match issue location", str(cm.exception))

    def test_block_cross_department_assignment(self):
        # Different department
        health_dept = Department.objects.create(name="Health", level="village")
        
        issue = Issue.objects.create(
            reported_by=self.citizen,
            title="Medical emergency",
            category="health", # Mapped to Health dept? Actually model uses department FK
            location=self.pune_village,
            photo1="test.jpg"
        )
        issue.department = health_dept
        issue.save()
        
        # Try to assign Road officer to Health issue
        issue.assigned_to = self.pune_officer
        
        with self.assertRaises(ValidationError) as cm:
            issue.save()
            
        self.assertIn("Cross-department assignment NOT allowed", str(cm.exception))
