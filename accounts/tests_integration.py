from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from accounts.models import Department, Location, StaffingPolicy, StaffingRollout, DistrictOperationalCondition, OfficerProfile
from accounts.services import (
    analyze_district_coverage, 
    generate_staffing_for_district, 
    simulate_district_rollout,
    execute_approved_rollout
)

User = get_user_model()

class StaffingEngineTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Rural Development", level="village")
        self.dist = Location.objects.create(name="Pune", type="district")
        self.taluka = Location.objects.create(name="Haveli", type="taluka", parent=self.dist)
        # Create 10 villages
        for i in range(10):
            Location.objects.create(name=f"Village {i}", type="village", parent=self.taluka)
            
    def test_policy_validation_ratio_limit(self):
        policy = StaffingPolicy(
            department=self.dept,
            level="village",
            is_rural=True,
            ratio=1000, # Unrealistic
            designation="Gram Sevak"
        )
        with self.assertRaises(ValidationError):
            policy.full_clean()

    def test_staffing_rollout_lifecycle(self):
        # 1. Define Policy (1 officer per 5 villages)
        StaffingPolicy.objects.create(
            department=self.dept,
            level="village",
            is_rural=True,
            ratio=5,
            designation="Gram Sevak"
        )
        
        # 2. Simulate Rollout
        rollout = simulate_district_rollout("Pune")
        self.assertEqual(rollout.estimated_officers, 2) # 10 villages / 5 ratio = 2
        self.assertEqual(rollout.status, StaffingRollout.Status.DRAFT)
        
        # 3. Approve Rollout
        rollout.status = StaffingRollout.Status.APPROVED
        rollout.save()
        
        # 4. Execute Rollout
        execute_approved_rollout(rollout.id, limit=10)
        
        # 5. Verify Officers Created
        self.assertEqual(OfficerProfile.objects.filter(location=self.taluka).count(), 2)
        rollout.refresh_from_db()
        self.assertEqual(rollout.status, StaffingRollout.Status.COMPLETED)

class DynamicSLATests(TestCase):
    def setUp(self):
        from issues.models import Issue
        self.citizen = User.objects.create_user(username="c1", email="c1@a.com", role="citizen")
        self.dist = Location.objects.create(name="Nagpur", type="district")
        self.taluka = Location.objects.create(name="N-Taluka", type="taluka", parent=self.dist)
        self.village = Location.objects.create(name="N-Village", type="village", parent=self.taluka)
        
    def test_sla_multiplier_during_monsoon(self):
        from issues.models import Issue
        
        # 'burst' and 'danger' trigger High priority (2 days)
        issue = Issue.objects.create(
            reported_by=self.citizen,
            title="DANGER: Pipe Burst",
            category="water_leakage",
            location=self.village,
            photo1="dummy.jpg"
        )
        self.assertEqual(issue.priority, "high")
        self.assertEqual(issue.sla_days, 2.0)
        
        # Activate Monsoon in Nagpur
        DistrictOperationalCondition.objects.create(
            district=self.dist,
            type="monsoon",
            sla_multiplier=1.5,
            is_active=True
        )
        
        # SLA should now be 2 * 1.5 = 3.0
        self.assertEqual(issue.sla_days, 3.0)
