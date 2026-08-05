import os
import django
import sys
import csv
import random
import string
from django.db import connection
from django.contrib.auth.hashers import identify_hasher, is_password_usable, make_password, check_password
from django.utils import timezone
from django.db.models import Count

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from issues.models import Issue

def generate_temp_password():
    digits = ''.join(random.choices(string.digits, k=6))
    return f"GovTemp@{digits}"

def validate_hash(pwd_hash):
    if not pwd_hash:
        return False, "NULL_HASH"
    try:
        identify_hasher(pwd_hash)
        if not is_password_usable(pwd_hash):
            return False, "UNUSABLE_HASH"
        # Check if it crashes on check_password
        check_password("dummy_pwd_test", pwd_hash)
        return True, "PASSWORD_OK"
    except Exception as e:
        return False, f"INVALID_CREDENTIAL_STATE: {str(e)}"

def run_audit():
    print("Starting Authentication Integrity & Login Validation Audit...")
    
    results = []
    summary = {
        "total_checked": 0,
        "successful_logins_simulated": 0, # We can't actually login, but we can check if hash is valid
        "failed_logins": 0,
        "invalid_hashes": 0,
        "temp_passwords_issued": 0,
        "duplicate_emails": 0,
        "orphan_profiles": 0,
        "inactive_accounts": 0
    }

    # Detect duplicates
    email_counts = {}
    username_counts = {}

    all_users = User.objects.all()
    for u in all_users:
        if u.email:
            email_counts[u.email.lower()] = email_counts.get(u.email.lower(), 0) + 1
        if u.username:
            username_counts[u.username.lower()] = username_counts.get(u.username.lower(), 0) + 1

    profiles = [
        ("Citizen", CitizenProfile.objects.all().select_related('user')),
        ("Officer", OfficerProfile.objects.all().select_related('user', 'department')),
        ("Admin", AdminProfile.objects.all().select_related('user', 'department'))
    ]

    for role_name, queryset in profiles:
        for profile in queryset:
            summary["total_checked"] += 1
            
            # Orphan Check
            is_orphan = False
            try:
                user = profile.user
            except User.DoesNotExist:
                is_orphan = True
                summary["orphan_profiles"] += 1

            # Field Validation
            username = profile.username or (user.username if not is_orphan else "N/A")
            email = profile.email or (user.email if not is_orphan else "N/A")
            pwd_hash = profile.password_hash
            is_active = profile.is_active
            
            if not is_active:
                summary["inactive_accounts"] += 1

            # Duplicate Check
            is_duplicate_email = email_counts.get(email.lower(), 0) > 1 if email != "N/A" else False
            if is_duplicate_email:
                summary["duplicate_emails"] += 1

            # Hash Validation
            hash_valid, hash_status = validate_hash(pwd_hash)
            
            auth_status = "AUTHENTICATED" if hash_valid and is_active else "FAILED"
            if not is_active:
                auth_status = "INACTIVE"
            if is_orphan:
                auth_status = "ORPHANED_PROFILE"
            if not hash_valid:
                auth_status = "INVALID_CREDENTIAL_STATE"
                summary["invalid_hashes"] += 1

            password_status = hash_status
            temp_pwd_issued = "NO"
            temp_pwd = ""

            if not hash_valid and auth_status != "ORPHANED_PROFILE":
                temp_pwd = generate_temp_password()
                profile.password_hash = make_password(temp_pwd)
                # Note: We are saving to DB as requested: "ONLY reset passwords for BROKEN/CORRUPTED accounts."
                profile.save()
                temp_pwd_issued = "YES"
                summary["temp_passwords_issued"] += 1
                password_status = "PASSWORD_RESET_REQUIRED"

            # Issue Counts
            citizen_issue_count = 0
            officer_assigned_count = 0
            admin_dept = "N/A"

            if role_name == "Citizen":
                if not is_orphan:
                    citizen_issue_count = Issue.objects.filter(reported_by=user).count()
            elif role_name == "Officer":
                officer_assigned_count = Issue.objects.filter(assigned_to=profile).count()
            elif role_name == "Admin":
                admin_dept = profile.department.name if profile.department else "N/A"

            last_login = profile.last_login.strftime("%Y-%m-%d %H:%M:%S") if profile.last_login else "Never"

            results.append({
                "Role": role_name,
                "Username": username,
                "Email": email,
                "Auth Status": auth_status,
                "Password Status": password_status,
                "Temporary Password Issued?": temp_pwd_issued,
                "Temp Password": temp_pwd, # For CSV/Internal use, maybe don't put in MD?
                "Citizen Issue Count": citizen_issue_count,
                "Officer Assigned Count": officer_assigned_count,
                "Admin Department": admin_dept,
                "Last Login": last_login,
                "Active Status": "Active" if is_active else "Inactive"
            })

    # Export CSV
    with open("AUTH_VALIDATION_AUDIT.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    # Export MD
    with open("AUTH_VALIDATION_AUDIT.md", "w") as f:
        f.write("# AUTHENTICATION INTEGRITY & LOGIN VALIDATION AUDIT\n\n")
        f.write(f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## FINAL SUMMARY\n\n")
        f.write(f"- Total accounts checked: {summary['total_checked']}\n")
        f.write(f"- Successful Hash Validations: {summary['total_checked'] - summary['invalid_hashes']}\n")
        f.write(f"- Failed Logins (Inactive/Orphan/Invalid Hash): {summary['invalid_hashes'] + summary['orphan_profiles'] + summary['inactive_accounts']}\n")
        f.write(f"- Invalid Hashes detected: {summary['invalid_hashes']}\n")
        f.write(f"- Temporary passwords issued: {summary['temp_passwords_issued']}\n")
        f.write(f"- Duplicate emails detected: {summary['duplicate_emails']}\n")
        f.write(f"- Orphan profiles detected: {summary['orphan_profiles']}\n\n")

        f.write("## AUDIT LOG\n\n")
        f.write("| Role | Username | Email | Auth Status | Password Status | Temp Pwd Issued? | Issues Reported | Assigned | Admin Dept | Last Login | Status |\n")
        f.write("|------|----------|-------|-------------|-----------------|------------------|-----------------|----------|------------|------------|--------|\n")
        for r in results:
            f.write(f"| {r['Role']} | {r['Username']} | {r['Email']} | {r['Auth Status']} | {r['Password Status']} | {r['Temporary Password Issued?']} | {r['Citizen Issue Count']} | {r['Officer Assigned Count']} | {r['Admin Department']} | {r['Last Login']} | {r['Active Status']} |\n")

    print("Audit complete. Reports generated: AUTH_VALIDATION_AUDIT.md, AUTH_VALIDATION_AUDIT.csv")

if __name__ == "__main__":
    run_audit()
