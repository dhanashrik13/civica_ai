from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

from .models import Department, OfficerProfile, AssignmentLog, Location, StaffingPolicy, StaffingRollout, CitizenProfile, AdminProfile

from django.utils.html import format_html

from .forms import CitizenPasswordChangeForm, OfficerPasswordChangeForm, AdminPasswordChangeForm

def masked_password_preview(obj):
    if obj.password_hash:
        parts = obj.password_hash.split('$')
        if len(parts) > 1:
            return f"{parts[0]}$********"
    return "********"

@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    form = CitizenPasswordChangeForm
    list_display = ('user', 'username', 'email', 'full_name', 'is_active', 'verification_status', 'trust_score')
    search_fields = ('username', 'email', 'user__username', 'full_name', 'phone_number', 'voter_id')
    list_filter = ('is_active', 'verification_status', 'citizen_status', 'gender', 'district', 'city', 'disability_status')
    readonly_fields = ('masked_password', 'trust_score', 'total_reports', 'valid_reports', 'rejected_reports', 'spam_reports', 'last_reported_at', 'created_at', 'updated_at')

    @admin.display(description='Password Hash (Masked)')
    def masked_password(self, obj):
        return masked_password_preview(obj)

    fieldsets = (
        ("Direct Authentication Fields (Migrated)", {
            "fields": ("username", "email", "masked_password", "is_active", "last_login", "created_at", "updated_at")
        }),
        ("Secure Password Management", {
            "fields": ("new_password", "confirm_password", "generate_temp_password")
        }),
        ("Identity", {
            "fields": ("user", "profile_photo", "first_name", "middle_name", "last_name", "full_name", "gender", "date_of_birth", "age")
        }),
        ("Contact", {
            "fields": ("phone_number", "phone", "alternate_phone_number", "emergency_contact_name", "emergency_contact_number")
        }),
        ("Governance Area", {
            "fields": ("address", "landmark", "village", "taluka", "district", "ward", "city", "state", "pincode", "latitude", "longitude")
        }),
        ("Citizen Governance Info", {
            "fields": ("aadhaar_last4", "voter_id", "preferred_language", "occupation", "education", "income_range", "family_size")
        }),
        ("Civic Trust & Reporting (Derived from Issue table)", {
            "fields": ("trust_score", "verification_status", "citizen_status", "total_reports", "valid_reports", "rejected_reports", "spam_reports", "last_reported_at")
        }),
        ("Accessibility", {
            "fields": ("disability_status", "accessibility_settings", "special_assistance_required")
        }),
        ("System Metadata", {
            "fields": ("notes", "reporting_metadata", "demographic_safe_metadata", "report_quality_avg", "frustration_index")
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(user__role=User.Role.CITIZEN)

@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    form = AdminPasswordChangeForm
    list_display = ('user', 'username', 'email', 'full_name', 'department', 'authority_level', 'is_active')
    search_fields = ('username', 'email', 'user__username', 'full_name')
    list_filter = ('is_active', 'authority_level', 'department')
    readonly_fields = ('masked_password', 'created_at', 'updated_at')

    @admin.display(description='Password Hash (Masked)')
    def masked_password(self, obj):
        return masked_password_preview(obj)

    fieldsets = (
        ("Direct Authentication Fields (Migrated)", {
            "fields": ("username", "email", "masked_password", "is_active", "last_login", "created_at", "updated_at")
        }),
        ("Secure Password Management", {
            "fields": ("new_password", "confirm_password", "generate_temp_password")
        }),
        ("Basic Info", {
            "fields": ("user", "full_name", "phone_no", "department", "authority_level")
        }),
        ("Permissions & Control", {
            "fields": ("override_permissions", "jurisdiction_scope", "emergency_privileges", "audit_privileges", "governance_control_metadata")
        }),
    )

@admin.register(OfficerProfile)
class OfficerAdmin(admin.ModelAdmin):
    form = OfficerPasswordChangeForm
    list_display = (
        'id', 'employee_id', 'username', 'email', 'full_name', 'department', 'level', 
        'is_active', 'assignment_health', 'hierarchy_preview', 'verification_badge'
    )
    list_filter = ('is_active', 'level', 'field_vs_desk', 'workload_category', 'duty_status', 'geo_assignment_integrity')
    search_fields = ('username', 'email', 'employee_id', 'full_name', 'official_email', 'user__username', 'phone')
    readonly_fields = ('masked_password', 'hierarchy_preview', 'reporting_chain_visibility', 'assignment_health', 'missing_data_warnings', 'pressure_status', 'created_at', 'updated_at')
    
    @admin.display(description='Password Hash (Masked)')
    def masked_password(self, obj):
        return masked_password_preview(obj)

    fieldsets = (
        ("Direct Authentication Fields (Migrated)", {
            "fields": ("username", "email", "masked_password", "is_active", "last_login", "created_at", "updated_at")
        }),
        ("Secure Password Management", {
            "fields": ("new_password", "confirm_password", "generate_temp_password")
        }),
        ("Basic Info", {
            "fields": ("user", "employee_id", "full_name", "department", "designation", "specialization", "joining_date")
        }),
        ("Governance & Hierarchy", {
            "fields": ("level", "location", "district", "taluka", "city", "zone", "ward", "village", "jurisdiction_scope", "hierarchy_preview")
        }),
        ("Reporting & Escalation", {
            "fields": ("reporting_officer", "reporting_chain_visibility", "escalation_authority", "escalation_reachability")
        }),
        ("Operational Realism", {
            "fields": ("duty_status", "shift_type", "workload_category", "workload_capacity", "field_vs_desk", "emergency_response_eligibility", "disaster_response_role", "response_priority_level")
        }),
        ("Contact & Traceability", {
            "fields": ("official_email", "phone", "alternate_contact", "emergency_contact", "office_location", "office_address", "multilingual_capability", "verified_communication_metadata", "administrative_audit_linkage")
        }),
        ("Metrics & Health", {
            "fields": ("geo_assignment_integrity", "verification_status", "missing_data_warnings", "assignment_health", "fatigue_level", "active_assigned_count", "pressure_status")
        }),
    )

    @admin.display(description='Hierarchy')
    def hierarchy_preview(self, obj):
        parts = [p for p in [obj.district, obj.taluka or obj.city, obj.village or obj.zone or obj.ward] if p]
        if not parts:
            return format_html('<span style="color:red;">Invalid/Missing Hierarchy</span>')
        return " ➔ ".join(parts)

    @admin.display(description='Reporting Chain')
    def reporting_chain_visibility(self, obj):
        if obj.reporting_officer:
            return format_html('<a href="{}">{} ({})</a>', 
                f"/admin/accounts/officer/{obj.reporting_officer.id}/change/",
                obj.reporting_officer.full_name or obj.reporting_officer.user.username,
                obj.reporting_officer.level
            )
        return format_html('<span style="color:orange;">Top Level / Unassigned</span>')

    @admin.display(description='Health')
    def assignment_health(self, obj):
        if obj.active_assigned_count > 50:
            return format_html('<span style="color:red; font-weight:bold;">Overloaded ({} cases)</span>', obj.active_assigned_count)
        if obj.geo_assignment_integrity != "Valid":
            return format_html('<span style="color:red; font-weight:bold;">Hierarchy Mismatch</span>')
        if not obj.reporting_officer and obj.level != 'district':
            return format_html('<span style="color:orange; font-weight:bold;">Orphaned</span>')
        return format_html('<span style="color:green;">Healthy</span>')

    @admin.display(description='Verification')
    def verification_badge(self, obj):
        if obj.verification_status == "Verified":
            return format_html('<span style="background:green; color:white; padding:2px 5px; border-radius:3px;">Verified</span>')
        return format_html('<span style="background:orange; color:white; padding:2px 5px; border-radius:3px;">Pending</span>')

    @admin.display(description='Missing Data')
    def missing_data_warnings(self, obj):
        missing = []
        if not obj.reporting_officer and obj.level != 'district': missing.append('Reporting OfficerProfile')
        if obj.level == 'village' and not obj.village: missing.append('Village Missing')
        if obj.level == 'ward' and not obj.ward: missing.append('Ward Missing')
        if obj.level == 'taluka' and not obj.taluka: missing.append('Taluka Missing')
        if not obj.official_email: missing.append('Official Email')
        if not obj.employee_id: missing.append('Employee ID')
        
        if missing:
            return format_html('<ul style="color:red; margin:0; padding-left:15px;"><li>{}</li></ul>', "</li><li>".join(missing))
        return format_html('<span style="color:green;">Complete</span>')
admin.site.register(Location)
admin.site.register(AssignmentLog)
User = get_user_model()




# ==================================================
# CUSTOM USER ADMIN
# ==================================================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "id",
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
        "is_approved",
    )

    list_filter = ("role", "is_active", "is_staff", "is_superuser", "is_approved")
    search_fields = ("username", "email", "_legacy_full_name")
    ordering = ("username",)

    fieldsets = (
        ("Login Info", {
            "fields": ("username", "password")
        }),
        ("Personal Info", {
            "fields": ("_legacy_full_name", "email", "_legacy_phone_no", "_legacy_address")
        }),
        ("Role & Permissions", {
            "fields": ("role", "is_active", "is_staff", "is_superuser", "is_approved", "groups", "user_permissions")
        }),
        ("Important Dates", {
            "fields": ("last_login", "date_joined")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "role"),
        }),
    )


# ==================================================
# DEPARTMENT ADMIN
# ==================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "level", "description")
    search_fields = ("name",)
    list_filter = ("level",)


@admin.register(StaffingPolicy)
class StaffingPolicyAdmin(admin.ModelAdmin):
    list_display = ("department", "level", "is_rural", "target_district", "version", "is_active", "designation")
    list_filter = ("is_active", "is_rural", "level", "department", "version")
    search_fields = ("department__name", "designation", "target_district__name")
    ordering = ("-version", "department")


@admin.register(StaffingRollout)
class StaffingRolloutAdmin(admin.ModelAdmin):
    list_display = ("id", "district", "status", "estimated_officers", "actual_officers_created", "created_at")
    list_filter = ("status", "district")
    readonly_fields = ("policy_snapshot", "created_at", "updated_at")



