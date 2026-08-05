from django.contrib.auth.models import AbstractUser, Group, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserManager(DjangoUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "citizen")
        return super().create_user(username, email=email, password=password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "super_admin")
        extra_fields.setdefault("is_approved", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        OFFICER = "officer", "OfficerProfile"
        DEPT_ADMIN = "dept_admin", "Department Admin"
        SUPER_ADMIN = "super_admin", "Super Admin"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN, db_index=True)
    
    # Legacy fields maintained for backward compatibility (Migration 0035)
    _legacy_department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="legacy_admins", db_column='department_id')
    _legacy_full_name = models.CharField(max_length=150, db_column='full_name')
    _legacy_phone_no = models.CharField(max_length=15, blank=True, db_column='phone_no')
    _legacy_address = models.CharField(max_length=200, blank=True, db_column='address')
    
    is_approved = models.BooleanField(default=False, db_index=True)
    
    _legacy_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='latitude')
    _legacy_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, db_column='longitude')
    _legacy_city = models.CharField(max_length=100, blank=True, db_column='city')
    _legacy_state = models.CharField(max_length=100, blank=True, db_column='state')

    REQUIRED_FIELDS = ["email"]
    objects = UserManager()

    class Meta:
        ordering = ["username"]

    @property
    def full_name(self):
        """Unified full_name property that delegates to specific profiles."""
        if self.role == self.Role.OFFICER and hasattr(self, 'officer'):
            return self.officer.full_name or self._legacy_full_name
        if self.role == self.Role.CITIZEN and hasattr(self, 'citizen_profile'):
            return self.citizen_profile.full_name or self._legacy_full_name
        if (self.role == self.Role.DEPT_ADMIN or self.role == self.Role.SUPER_ADMIN) and hasattr(self, 'admin_profile'):
            return self.admin_profile.full_name or self._legacy_full_name
        return self._legacy_full_name

    @full_name.setter
    def full_name(self, value):
        self._legacy_full_name = value

    @property
    def department(self):
        """Unified department property that delegates to specific profiles."""
        if (self.role == self.Role.DEPT_ADMIN or self.role == self.Role.SUPER_ADMIN) and hasattr(self, 'admin_profile'):
            return self.admin_profile.department
        if self.role == self.Role.OFFICER and hasattr(self, 'officer'):
            return self.officer.department
        return self._legacy_department

    @property
    def phone(self):
        """Unified phone property that delegates to specific profiles."""
        if self.role == self.Role.OFFICER and hasattr(self, 'officer'):
            return self.officer.phone or self._legacy_phone_no
        if self.role == self.Role.DEPT_ADMIN or self.role == self.Role.SUPER_ADMIN:
            admin_profile = getattr(self, 'admin_profile', None)
            if admin_profile:
                return admin_profile.phone_no or self._legacy_phone_no
        return self._legacy_phone_no

    @property
    def address(self):
        """Unified address property that delegates to specific profiles."""
        if self.role == self.Role.OFFICER and hasattr(self, 'officer'):
            return self.officer.address or self._legacy_address
        return self._legacy_address

    def save(self, *args, **kwargs):
        if self.pk:
            old_user = User.objects.get(pk=self.pk)
            # BLOCK Privilege Escalation: Prevent CITIZEN/OFFICER from becoming ADMIN via .save()
            if old_user.role in [self.Role.CITIZEN, self.Role.OFFICER] and self.role in [self.Role.SUPER_ADMIN, self.Role.DEPT_ADMIN]:
                if not kwargs.get('force_escalation', False):
                    self.role = old_user.role # Revert

        if self.is_superuser:
            self.role = self.Role.SUPER_ADMIN
            self.is_staff = True
            self.is_approved = True
        else:
            self.is_staff = self.role in [self.Role.SUPER_ADMIN, self.Role.DEPT_ADMIN]

        super().save(*args, **kwargs)
        self._sync_role_group()

    def _sync_role_group(self):
        try:
            group, _ = Group.objects.get_or_create(name=self.role.title())
            self.groups.clear()
            self.groups.add(group)
        except: pass

    def has_role(self, *roles): return self.role in roles
    @property
    def is_citizen(self): return self.role == self.Role.CITIZEN
    @property
    def is_officer(self): return self.role == self.Role.OFFICER
    @property
    def is_dept_admin(self): return self.role == self.Role.DEPT_ADMIN
    @property
    def is_super_admin(self): return self.role == self.Role.SUPER_ADMIN

    @property
    def dashboard_url_name(self):
        dashboard_map = {
            self.Role.CITIZEN: "dashboards:citizen_dashboard",
            self.Role.OFFICER: "dashboards:officer_dashboard",
            self.Role.DEPT_ADMIN: "dashboards:admin_dashboard",
            self.Role.SUPER_ADMIN: "dashboards:admin_dashboard",
        }
        return dashboard_map.get(self.role, "landing:home")

    def __str__(self): return f"{self.username} ({self.role})"


class Department(models.Model):
    class Level(models.TextChoices):
        VILLAGE = "village", "Village"
        TALUKA = "taluka", "Taluka"
        DISTRICT = "district", "District"
        CITY = "city", "City"
        ZONE = "zone", "Zone"
        WARD = "ward", "Ward"

    name = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.VILLAGE, db_index=True)
    description = models.TextField(blank=True)
    keywords = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self): return f"{self.name} ({self.get_level_display()})"


class Location(models.Model):
    class Type(models.TextChoices):
        VILLAGE = "village", "Village"
        TALUKA = "taluka", "Taluka"
        DISTRICT = "district", "District"
        CITY = "city", "City"
        ZONE = "zone", "Zone"
        WARD = "ward", "Ward"

    name = models.CharField(max_length=100, db_index=True)
    type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children", db_index=True)

    class Meta:
        ordering = ["type", "name"]
        indexes = [
            models.Index(fields=['type', 'parent']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.parent:
            if self.parent == self:
                raise ValidationError("A location cannot be its own parent.")
            # Check for circular dependency
            curr = self.parent
            while curr:
                if curr.id == self.id:
                    raise ValidationError("Circular hierarchy dependency detected.")
                curr = curr.parent

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.delete("global_location_payload_v2")

    def __str__(self): return f"{self.name} ({self.type})"


class OfficerProfile(models.Model):
    class Level(models.TextChoices):
        VILLAGE = "village", "Village"
        TALUKA = "taluka", "Taluka"
        DISTRICT = "district", "District"
        CITY = "city", "City"
        ZONE = "zone", "Zone"
        WARD = "ward", "Ward"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="officer")
    
    # Auth Domain Refactor: REAL DATABASE FIELDS
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(db_index=True, null=True, blank=True)
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    department = models.ForeignKey("Department", on_delete=models.CASCADE)
    location = models.ForeignKey("Location", on_delete=models.CASCADE)
    
    full_name = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True)
    zone = models.CharField(max_length=100, blank=True, null=True)
    ward = models.CharField(max_length=100, blank=True)

    village = models.CharField(max_length=100, blank=True)
    taluka = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, db_index=True)

    # Operational Realism: Human Behavior Metrics (Migration 0034)
    fatigue_level = models.IntegerField(default=0, help_text="0-100: Impacted by workload and duration of active duty")
    reliability_score = models.IntegerField(default=100, help_text="0-100: Degrades with missed SLAs and reassignment disputes")
    burnout_risk = models.FloatField(default=0.0, help_text="Probability of delayed response based on current pressure")
    last_active_at = models.DateTimeField(auto_now=True)
    active_assigned_count = models.IntegerField(default=0)
    
    # Additional Fields from Migration 0034
    administrative_audit_linkage = models.CharField(blank=True, max_length=100, null=True)
    alternate_contact = models.CharField(blank=True, max_length=15, null=True)
    disaster_response_role = models.CharField(blank=True, max_length=100, null=True)
    duty_status = models.CharField(blank=True, max_length=50, null=True)
    emergency_contact = models.CharField(blank=True, max_length=15, null=True)
    emergency_response_eligibility = models.BooleanField(default=False)
    escalation_authority = models.BooleanField(default=False)
    escalation_reachability = models.CharField(blank=True, max_length=50, null=True)
    field_vs_desk = models.CharField(blank=True, max_length=50, null=True)
    geo_assignment_integrity = models.CharField(blank=True, max_length=50, null=True)
    joining_date = models.DateField(blank=True, null=True)
    jurisdiction_scope = models.CharField(blank=True, max_length=100, null=True)
    multilingual_capability = models.CharField(blank=True, max_length=200, null=True)
    office_address = models.TextField(blank=True, null=True)
    office_location = models.CharField(blank=True, max_length=100, null=True)
    official_email = models.EmailField(blank=True, max_length=254, null=True)
    reporting_officer = models.ForeignKey("self", blank=True, null=True, on_delete=models.SET_NULL, related_name="subordinates")
    response_priority_level = models.IntegerField(default=3)
    service_region = models.CharField(blank=True, max_length=100, null=True)
    shift_type = models.CharField(blank=True, max_length=50, null=True)
    specialization = models.CharField(blank=True, max_length=100, null=True)
    verification_status = models.CharField(blank=True, max_length=50, null=True)
    verified_communication_metadata = models.JSONField(blank=True, default=dict)
    workload_capacity = models.IntegerField(default=10)
    workload_category = models.CharField(blank=True, max_length=50, null=True)

    class Meta:
        ordering = ["user__username"]
        indexes = [
            models.Index(fields=['location', 'department', 'level']),
            models.Index(fields=['district', 'taluka', 'village']),
            models.Index(fields=['city', 'zone', 'ward']),
            models.Index(fields=['fatigue_level', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def pressure_level(self):
        """Returns a percentage representing the current operational pressure."""
        workload_score = min((self.active_assigned_count / float(self.workload_capacity)) * 100, 100) if self.workload_capacity > 0 else 100
        return int((workload_score * 0.5) + (self.fatigue_level * 0.5))

    @property
    def pressure_status(self):
        p = self.pressure_level
        if p > 80: return "Critical"
        if p > 60: return "High"
        if p > 30: return "Moderate"
        return "Stable"

    @property
    def assignment_health(self):
        if self.active_assigned_count > self.workload_capacity: return "Overloaded"
        if self.fatigue_level > 70: return "Fatigued"
        return "Healthy"

    @property
    def verification_badge(self):
        if self.verification_status == "Verified": return "✅ Verified"
        return "⚠️ Pending"

    def __str__(self): return self.full_name or self.user.get_full_name() or self.user.username


# Compatibility Alias
Officer = OfficerProfile


class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    
    # Auth Domain Refactor: REAL DATABASE FIELDS
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(db_index=True, null=True, blank=True)
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_profiles")
    full_name = models.CharField(max_length=150, blank=True)
    phone_no = models.CharField(max_length=15, blank=True)
    authority_level = models.IntegerField(default=1)
    override_permissions = models.JSONField(default=dict, blank=True)
    jurisdiction_scope = models.CharField(max_length=100, blank=True)
    emergency_privileges = models.BooleanField(default=False)
    audit_privileges = models.BooleanField(default=False)
    governance_control_metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Admin: {self.full_name or self.user.username}"


class OfficerAbsence(models.Model):
    class Reason(models.TextChoices):
        LEAVE = "leave", "Planned Leave"
        SICKNESS = "sick", "Sickness"
        EMERGENCY = "emergency", "Family Emergency"
        TRAINING = "training", "Government Training"
        TRANSFER = "transfer", "In-Transit (Transfer)"

    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name="absences")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_approved = models.BooleanField(default=False)
    substitute_officer = models.ForeignKey(OfficerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="substitutions")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.officer.user.username} - {self.reason} ({self.start_date} to {self.end_date})"


class CitizenProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        NOT_SPECIFIED = "not_specified", "Prefer not to say"

    class VerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        PENDING = "pending", "Verification Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    class CitizenStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        BANNED = "banned", "Banned"
        PENDING = "pending", "Pending Verification"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="citizen_profile")
    
    # Auth Domain Refactor: REAL DATABASE FIELDS
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(db_index=True, null=True, blank=True)
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    profile_photo = models.ImageField(upload_to="citizen_profiles/", null=True, blank=True, verbose_name="Profile Photo")
    first_name = models.CharField(max_length=50, blank=True, verbose_name="First Name")
    middle_name = models.CharField(max_length=50, blank=True, verbose_name="Middle Name")
    last_name = models.CharField(max_length=50, blank=True, verbose_name="Last Name")
    full_name = models.CharField(max_length=150, blank=True, verbose_name="Full Name")
    gender = models.CharField(max_length=20, choices=Gender.choices, default=Gender.NOT_SPECIFIED, verbose_name="Gender")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    age = models.IntegerField(null=True, blank=True, verbose_name="Age")
    
    phone_number = models.CharField(max_length=15, blank=True, db_index=True, verbose_name="Phone Number")
    phone = models.CharField(max_length=15, blank=True)
    alternate_phone_number = models.CharField(max_length=15, blank=True, verbose_name="Alternate Phone Number")
    # Redundant email field removed as it is now in the auth block
    emergency_contact_name = models.CharField(max_length=100, blank=True, verbose_name="Emergency Contact Name")
    emergency_contact_number = models.CharField(max_length=15, blank=True, verbose_name="Emergency Contact Number")
    
    address = models.TextField(blank=True, verbose_name="Address")
    landmark = models.CharField(max_length=100, blank=True, verbose_name="Landmark")
    village = models.CharField(max_length=100, blank=True, verbose_name="Village")
    taluka = models.CharField(max_length=100, blank=True, verbose_name="Taluka")
    district = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="District")
    ward = models.CharField(max_length=100, blank=True, verbose_name="Ward")
    city = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="City")
    state = models.CharField(max_length=100, blank=True, verbose_name="State")
    pincode = models.CharField(max_length=10, blank=True, verbose_name="Pincode")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")
    
    aadhaar_last4 = models.CharField(max_length=4, blank=True, verbose_name="Aadhaar (Last 4)")
    voter_id = models.CharField(max_length=20, blank=True, verbose_name="Voter ID")
    preferred_language = models.CharField(max_length=50, blank=True, verbose_name="Preferred Language")
    occupation = models.CharField(max_length=100, blank=True, verbose_name="Occupation")
    education = models.CharField(max_length=100, blank=True, verbose_name="Education")
    income_range = models.CharField(max_length=50, blank=True, verbose_name="Income Range")
    family_size = models.IntegerField(null=True, blank=True, verbose_name="Family Size")
    
    trust_score = models.IntegerField(default=50, db_index=True, verbose_name="Trust Score")
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.UNVERIFIED, db_index=True, verbose_name="Verification Status")
    citizen_status = models.CharField(max_length=20, choices=CitizenStatus.choices, default=CitizenStatus.ACTIVE, verbose_name="Citizen Status")
    total_reports = models.IntegerField(default=0, verbose_name="Total Reports")
    valid_reports = models.IntegerField(default=0, verbose_name="Valid Reports")
    rejected_reports = models.IntegerField(default=0, verbose_name="Rejected Reports")
    spam_reports = models.IntegerField(default=0, verbose_name="Spam Reports")
    last_reported_at = models.DateTimeField(null=True, blank=True, verbose_name="Last Reported At")
    
    disability_status = models.BooleanField(default=False, verbose_name="Disability Status")
    accessibility_settings = models.JSONField(default=dict, blank=True, verbose_name="Accessibility Settings")
    special_assistance_required = models.TextField(blank=True, verbose_name="Special Assistance Required")
    
    notes = models.TextField(blank=True, verbose_name="Notes")
    reporting_metadata = models.JSONField(default=dict, blank=True, verbose_name="Reporting Metadata")
    demographic_safe_metadata = models.JSONField(blank=True, default=dict, verbose_name='Demographic Safe Metadata')
    report_quality_avg = models.FloatField(default=0.5)
    frustration_index = models.FloatField(default=0.0)
    
    # Keep timestamps here but ensure they match auto_now/auto_now_add in auth block
    # Actually, they are already in the auth block at the top now.
    # I should remove the ones at the bottom to avoid confusion, or keep them if they are the same.
    # The ones at the top are:
    # created_at = models.DateTimeField(auto_now_add=True, null=True)
    # updated_at = models.DateTimeField(auto_now=True, null=True)
    # The ones at the bottom were:
    # created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    # updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    # I'll remove the ones at the bottom.

    def __str__(self): return f"{self.user.username} (Trust: {self.trust_score})"

@receiver(post_save, sender=User)
def create_citizen_profile(sender, instance, created, **kwargs):
    if created and instance.role == User.Role.CITIZEN:
        CitizenProfile.objects.get_or_create(user=instance)


class IssueImage(models.Model):
    from issues.validators import validate_secure_image
    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="issues/", validators=[validate_secure_image])


class AssignmentLog(models.Model):
    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="assignment_logs")
    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name="assignment_logs")
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="assigned")

    class Meta:
        ordering = ["-assigned_at"]


class StaffingPolicy(models.Model):
    department = models.ForeignKey("Department", on_delete=models.CASCADE, related_name="policies")
    level = models.CharField(max_length=20, choices=Department.Level.choices)
    is_rural = models.BooleanField(default=True, help_text="True for Rural (Village/Taluka), False for Urban (City/Zone/Ward)")
    ratio = models.IntegerField(default=0, help_text="1 officer per X villages (for rural village-level roles)")
    fixed_count = models.IntegerField(default=0, help_text="Fixed officers per unit (e.g., 1 per Ward, 1 per Zone)")
    designation = models.CharField(max_length=100)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(auto_now_add=True)
    target_district = models.ForeignKey("Location", on_delete=models.SET_NULL, null=True, blank=True, 
                                       limit_choices_to={'type': 'district'}, related_name="district_policies")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True, related_name="created_policies")

    class Meta:
        unique_together = ["department", "level", "is_rural", "target_district", "version"]
        verbose_name_plural = "Staffing Policies"
        ordering = ["-version", "department"]

    def clean(self):
        from .services import validate_staffing_policy
        validate_staffing_policy(self)

    def __str__(self):
        region = "Rural" if self.is_rural else "Urban"
        dist = f" [{self.target_district.name}]" if self.target_district else " [Global]"
        return f"{self.department.name} - {self.get_level_display()} ({region}){dist} v{self.version}"


class StaffingRollout(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft (Simulation)"
        APPROVED = "approved", "Approved for Rollout"
        COMPLETED = "completed", "Rollout Completed"
        FAILED = "failed", "Rollout Failed"

    district = models.ForeignKey("Location", on_delete=models.CASCADE, limit_choices_to={'type': 'district'})
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    policy_snapshot = models.JSONField(default=dict, help_text="Snapshot of active policies at time of simulation")
    estimated_officers = models.IntegerField(default=0)
    actual_officers_created = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_rollouts")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rollout: {self.district.name} ({self.get_status_display()})"


class PendingTask(models.Model):
    """
    Outbox Pattern: Ensures atomic task persistence before Celery dispatch.
    Eliminates non-deterministic task loss (WP-C1).
    """
    class Status(models.TextChoices):
        PENDING = "pending", "Pending Dispatch"
        DISPATCHED = "dispatched", "Dispatched to Broker"
        FAILED = "failed", "Permanent Failure"

    task_name = models.CharField(max_length=255)
    args = models.JSONField(default=list)
    kwargs = models.JSONField(default=dict)
    queue = models.CharField(max_length=50, default='default')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.task_name} ({self.status})"

class AuditLog(models.Model):
    class Action(models.TextChoices):
        POLICY_CHANGE = 'policy_change', 'Policy Change'
        ASSIGNMENT_OVERRIDE = 'assignment_override', 'Assignment Override'
        ESCALATION_APPEAL = 'escalation_appeal', 'Escalation Appeal'
        SECURITY_ALERT = 'security_alert', 'Security Alert'
        DATA_EXPORT = 'data_export', 'Data Export'
        GOVERNANCE_REPLAY = 'governance_replay', 'Governance Replay/Forensics'

    user = models.ForeignKey("User", on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=Action.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100, blank=True, null=True)
    details = models.JSONField(default=dict)
    state_snapshot = models.JSONField(default=dict, help_text="Snapshot of the resource state for forensic reconstruction")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp} - {self.user} - {self.action}"


class Incident(models.Model):
    class Severity(models.TextChoices):
        P0 = "p0", "CRITICAL - System Down"
        P1 = "p1", "HIGH - Major Degraded"
        P2 = "p2", "MEDIUM - Partial Issues"
        P3 = "p3", "LOW - Minor/Normal"

    class Status(models.TextChoices):
        OPEN = "open", "Investigating"
        MITIGATED = "mitigated", "Mitigated"
        RESOLVED = "resolved", "Resolved (Postmortem Pending)"
        CLOSED = "closed", "Closed (Postmortem Complete)"

    title = models.CharField(max_length=200)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.P2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    incident_type = models.CharField(max_length=100, help_text="e.g. REDIS_DOWN, QUEUE_CONGESTION")
    description = models.TextField()
    
    started_at = models.DateTimeField(default=timezone.now)
    mitigated_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    postmortem = models.TextField(blank=True)
    reproduction_steps = models.TextField(blank=True)
    
    impacted_district = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True)
    timeline = models.JSONField(default=list, help_text="Audit trail of incident events")

    def __str__(self):
        return f"INC-{self.id}: {self.title} ({self.severity})"

    def add_event(self, message):
        """Adds an event to the incident timeline"""
        self.timeline.append({
            "timestamp": timezone.now().isoformat(),
            "message": message
        })
        self.save()

    def generate_postmortem_summary(self):
        """Automates postmortem generation based on incident data"""
        mttr = self.mttr_seconds
        duration_str = f"{mttr/60:.2f} minutes" if mttr else "N/A"
        
        summary = [
            f"# POSTMORTEM: {self.title}",
            f"Severity: {self.get_severity_display()}",
            f"Duration: {duration_str}",
            f"Type: {self.incident_type}",
            "\n## Timeline",
        ]
        for event in self.timeline:
            summary.append(f"- [{event['timestamp']}] {event['message']}")
            
        summary.append("\n## Impact Analysis")
        summary.append(self.description)
        
        self.postmortem = "\n".join(summary)
        self.status = self.Status.CLOSED
        self.save()
        return self.postmortem

    @property
    def mttr_seconds(self):
        if self.resolved_at and self.started_at:
            return (self.resolved_at - self.started_at).total_seconds()
        return None


class OperationalMetric(models.Model):
    name = models.CharField(max_length=100)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=['name', 'timestamp'])]


class AdministrativeDirective(models.Model):
    class Type(models.TextChoices):
        VIP_PRIORITY = "vip", "VIP/Collector Priority"
        DISTRICT_EMERGENCY = "district_emergency", "District-Wide Emergency"
        POLICY_BYPASS = "policy_bypass", "Staffing Policy Bypass"
        LEGAL_DIRECTIVE = "legal", "Legal/Court Directive"

    type = models.CharField(max_length=50, choices=Type.choices)
    district = models.ForeignKey(Location, on_delete=models.CASCADE, limit_choices_to={'type': 'district'})
    authority_reference = models.CharField(max_length=200)
    justification = models.TextField()
    effective_from = models.DateTimeField(default=timezone.now)
    effective_to = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self): return f"{self.get_type_display()} - {self.district.name}"


class DistrictOperationalCondition(models.Model):
    class Type(models.TextChoices):
        MONSOON = "monsoon", "Active Monsoon"
        HEATWAVE = "heatwave", "Extreme Heatwave"
        STRIKE = "strike", "Administrative Strike"
        HOLIDAY = "holiday", "Public Holiday Period"
        CRISIS = "crisis", "Active Crisis/Emergency"

    district = models.ForeignKey(Location, on_delete=models.CASCADE, limit_choices_to={'type': 'district'})
    type = models.CharField(max_length=20, choices=Type.choices)
    sla_multiplier = models.FloatField(default=1.5)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self): return f"{self.district.name} - {self.get_type_display()}"


class SystemFailureEvent(models.Model):
    class Type(models.TextChoices):
        NETWORK = "network", "Regional Network Outage"
        POWER = "power", "Localized Power Failure"
        CONGESTION = "congestion", "Queue/Notification Congestion"
        MAINTENANCE = "maintenance", "Emergency System Maintenance"

    type = models.CharField(max_length=20, choices=Type.choices)
    district = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, limit_choices_to={'type': 'district'})
    is_active = models.BooleanField(default=True)
    impact_factor = models.FloatField(default=2.0)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        scope = self.district.name if self.district else "Global"
        return f"{self.get_type_display()} ({scope})"


class JurisdictionDispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Dispute Raised"
        ARBITRATION = "arbitration", "In Arbitration"
        RESOLVED = "resolved", "Responsibility Fixed"
        REJECTED = "rejected", "Dispute Dismissed"

    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="disputes")
    original_department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="disputes_raised")
    disputing_officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name="disputes_filed")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    arbitrator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="dispute_decisions")
    final_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="dispute_resolutions")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute: Issue #{self.issue.id} by {self.disputing_officer.user.username}"


class DisasterEvent(models.Model):
    class Type(models.TextChoices):
        FLOOD = "flood", "Severe Flooding"
        LANDSLIDE = "landslide", "Landslide/Collapse"
        EPIDEMIC = "epidemic", "Disease Outbreak"
        FIRE = "fire", "Major Urban Fire"
        CIVIL_UNREST = "civil", "Civil Unrest"

    district = models.ForeignKey(Location, on_delete=models.CASCADE, limit_choices_to={'type': 'district'})
    type = models.CharField(max_length=20, choices=Type.choices)
    is_declared = models.BooleanField(default=True)
    emergency_command_center = models.ForeignKey(OfficerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="command_center_disasters")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    def __str__(self): return f"Disaster: {self.get_type_display()} in {self.district.name}"

class HealthSnapshot(models.Model):
    """
    High-Fidelity Observability Data.
    Stores periodic snapshots of platform-wide operational health.
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Governance Health
    avg_readiness = models.FloatField(default=0.0)
    total_staff = models.IntegerField(default=0)
    pending_issues = models.IntegerField(default=0)
    pressure_index = models.FloatField(default=0.0)
    
    # Infrastructure Health
    outbox_backlog = models.IntegerField(default=0)
    failed_tasks = models.IntegerField(default=0)
    system_latency_ms = models.FloatField(default=0.0)
    
    # AI Trust
    avg_ai_confidence = models.FloatField(default=0.0)
    calibration_drift = models.FloatField(default=0.0)
    
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=['timestamp']),
        ]

    def __str__(self): return f"Health @ {self.timestamp}"

# Compatibility Alias
Officer = OfficerProfile

# Compatibility Alias
Officer = OfficerProfile
