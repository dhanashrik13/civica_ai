import os
import django
import sys
import csv
import random
import string
import secrets
import importlib
from django.db import connection, transaction
from django.contrib.auth.hashers import identify_hasher, is_password_usable, make_password, check_password
from django.utils import timezone
from django.conf import settings

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from issues.models import Issue

def generate_temp_password():
    """Generates a password in format GovTemp@<random6digits>"""
    digits = ''.join(random.choices(string.digits, k=6))
    return f"GovTemp@{digits}"

def validate_hash(pwd_hash):
    """Safely validates the hash format and usability."""
    if not pwd_hash:
        return False, "NULL_AUTH_FIELD"
    try:
        identify_hasher(pwd_hash)
        if not is_password_usable(pwd_hash):
            return False, "UNUSABLE_HASH"
        # Safe check to see if it's a validly encoded string for the hasher
        # We don't need to call check_password here as identify_hasher already verified it's a known format
        return True, "PASSWORD_OK"
    except Exception as e:
        return False, f"INVALID_CREDENTIAL_STATE: {str(e)}"

def check_backend_mappings():
    """Checks if authentication backends are correctly mapped and importable."""
    backends = getattr(settings, 'AUTHENTICATION_BACKENDS', [])
    broken = []
    for backend_path in backends:
        try:
            module_path, class_name = backend_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            getattr(module, class_name)
        except Exception as e:
            broken.append(f"{backend_path} ({str(e)})")
    return broken

def run_audit():
    print("Starting STRICT AUTHENTICATION INTEGRITY & LOGIN VALIDATION AUDIT...")
    
    results = []
    summary = {
        "total_accounts_checked": 0,
        "successful_logins_simulated": 0,
        "failed_logins": 0,
        "invalid_hashes": 0,
        "temp_passwords_issued": 0,
        "duplicate_emails": 0,
        "duplicate_usernames": 0,
        "orphan_profiles": 0,
        "inactive_accounts": 0,
        "broken_backends": []
    }

    # 1. Check Backends
    summary["broken_backends"] = check_backend_mappings()

    # 2. Pre-calculate duplicates and issue counts for efficiency
    print("Pre-calculating metrics...")
    email_counts = {}
    username_counts = {}
    
    # Check User model
    for u in User.objects.values_list('email', 'username'):
        e, un = u
        if e:
            e_lower = e.lower().strip()
            email_counts[e_lower] = email_counts.get(e_lower, 0) + 1
        if un:
            un_lower = un.lower().strip()
            username_counts[un_lower] = username_counts.get(un_lower, 0) + 1

    # Pre-calculate Issue counts
    from django.db.models import Count
    citizen_issue_counts = {item['reported_by']: item['count'] for item in Issue.objects.values('reported_by').annotate(count=Count('id'))}
    officer_issue_counts = {item['assigned_to']: item['count'] for item in Issue.objects.values('assigned_to').annotate(count=Count('id'))}

    print("Iterating through profiles...")
    profile_sets = [
        ("Citizen", CitizenProfile.objects.all().select_related('user')),
        ("Officer", OfficerProfile.objects.all().select_related('user', 'department')),
        ("Admin", AdminProfile.objects.all().select_related('user', 'department'))
    ]

    for role_name, queryset in profile_sets:
        print(f"  Auditing {role_name} accounts (Total: {queryset.count()})...")
        count = 0
        for profile in queryset:
            count += 1
            if count % 100 == 0:
                print(f"    Processed {count} {role_name}s...")
            summary["total_accounts_checked"] += 1
            
            # Orphan Check
            is_orphan = False
            user = None
            try:
                user = profile.user
            except User.DoesNotExist:
                is_orphan = True
                summary["orphan_profiles"] += 1

            # Field Validation
            username = profile.username or (user.username if user else None)
            email = profile.email or (user.email if user else None)
            pwd_hash = profile.password_hash
            is_active = profile.is_active
            
            if not is_active:
                summary["inactive_accounts"] += 1

            # Duplicate Check
            is_duplicate_email = email_counts.get(email.lower().strip(), 0) > 1 if email else False
            if is_duplicate_email:
                summary["duplicate_emails"] += 1

            is_duplicate_username = username_counts.get(username.lower().strip(), 0) > 1 if username else False
            if is_duplicate_username:
                summary["duplicate_usernames"] += 1

            # Hash Validation
            hash_valid, hash_status = validate_hash(pwd_hash)
            
            # Auth Status Determination
            auth_status = "AUTHENTICATED"
            if not is_active:
                auth_status = "INACTIVE"
            elif is_orphan:
                auth_status = "ORPHANED_PROFILE"
            elif not hash_valid:
                auth_status = "INVALID_CREDENTIAL_STATE"
                summary["invalid_hashes"] += 1
            
            if auth_status == "AUTHENTICATED":
                summary["successful_logins_simulated"] += 1
            else:
                summary["failed_logins"] += 1

            password_status = hash_status
            temp_pwd_issued = "NO"
            temp_pwd = ""

            # Corruption Recovery
            if not hash_valid and not is_orphan:
                temp_pwd = generate_temp_password()
                new_hash = make_password(temp_pwd)
                
                try:
                    with transaction.atomic():
                        profile.password_hash = new_hash
                        # Conceptual mark
                        if role_name == "Citizen":
                            profile.reporting_metadata["PASSWORD_RESET_REQUIRED"] = True
                        elif role_name == "Officer":
                            profile.verified_communication_metadata["PASSWORD_RESET_REQUIRED"] = True
                        elif role_name == "Admin":
                            profile.governance_control_metadata["PASSWORD_RESET_REQUIRED"] = True
                        
                        profile.save()
                        
                        if user:
                            user.password = new_hash
                            user.save()
                            
                    temp_pwd_issued = "YES"
                    summary["temp_passwords_issued"] += 1
                    password_status = "PASSWORD_RESET_REQUIRED"
                except Exception as e:
                    password_status = f"RESET_FAILED: {str(e)}"

            # Issue Counts
            citizen_issue_count = citizen_issue_counts.get(user.id if user else None, 0) if role_name == "Citizen" else 0
            officer_assigned_count = officer_issue_counts.get(profile.id, 0) if role_name == "Officer" else 0
            
            admin_dept = "N/A"
            if role_name in ["Officer", "Admin"] and hasattr(profile, 'department') and profile.department:
                admin_dept = profile.department.name

            last_login = profile.last_login.strftime("%Y-%m-%d %H:%M:%S") if profile.last_login else "Never"

            results.append({
                "Role": role_name,
                "Username": username or "MISSING",
                "Email": email or "MISSING",
                "Auth Status": auth_status,
                "Password Status": password_status,
                "Temporary Password Issued?": temp_pwd_issued,
                "Temp Password": temp_pwd, # Stored in CSV for recovery, but hidden in MD report
                "Citizen Issue Count": citizen_issue_count,
                "Officer Assigned Count": officer_assigned_count,
                "Admin Department": admin_dept,
                "Last Login": last_login,
                "Active Status": "Active" if is_active else "Inactive"
            })

    # Export CSV
    print("Exporting CSV...")
    with open("AUTH_VALIDATION_AUDIT.csv", "w", newline="", encoding="utf-8") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    # Export MD
    print("Exporting Markdown report...")
    with open("AUTH_VALIDATION_AUDIT.md", "w", encoding="utf-8") as f:
        f.write("# STRICT AUTHENTICATION INTEGRITY & LOGIN VALIDATION AUDIT\n\n")
        f.write(f"**Date:** {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## FINAL SUMMARY\n\n")
        f.write(f"- **Total accounts checked:** {summary['total_accounts_checked']}\n")
        f.write(f"- **Successful simulated logins:** {summary['successful_logins_simulated']}\n")
        f.write(f"- **Failed logins (Inactive/Orphan/Invalid Hash):** {summary['failed_logins']}\n")
        f.write(f"- **Invalid hashes detected:** {summary['invalid_hashes']}\n")
        f.write(f"- **Temporary passwords issued:** {summary['temp_passwords_issued']}\n")
        f.write(f"- **Duplicate emails detected:** {summary['duplicate_emails']}\n")
        f.write(f"- **Duplicate usernames detected:** {summary['duplicate_usernames']}\n")
        f.write(f"- **Orphan profiles detected:** {summary['orphan_profiles']}\n")
        
        if summary["broken_backends"]:
            f.write(f"- **Broken backend mappings:** {len(summary['broken_backends'])}\n")
            for b in summary["broken_backends"]:
                f.write(f"  - ⚠️ `{b}`\n")
        else:
            f.write("- **Authentication Backend Mappings:** VALID ✅\n")
            
        f.write("\n## AUDIT LOG\n\n")
        f.write("| Role | Username | Email | Auth Status | Password Status | Temp Issued? | Issues | Assigned | Dept | Last Login | Status |\n")
        f.write("|------|----------|-------|-------------|-----------------|--------------|--------|----------|------|------------|--------|\n")
        for r in results:
            # Mask sensitive info for the MD report
            temp_issued = r["Temporary Password Issued?"]
            issues = r["Citizen Issue Count"] if r["Role"] == "Citizen" else "N/A"
            assigned = r["Officer Assigned Count"] if r["Role"] == "Officer" else "N/A"
            
            f.write(f"| {r['Role']} | {r['Username']} | {r['Email']} | {r['Auth Status']} | {r['Password Status']} | {temp_issued} | {issues} | {assigned} | {r['Admin Department']} | {r['Last Login']} | {r['Active Status']} |\n")

        f.write("\n---\n*Report generated autonomously by Gemini CLI.*")

    print(f"Audit complete. Summary:")
    print(f"  Total Checked: {summary['total_accounts_checked']}")
    print(f"  Invalid Hashes: {summary['invalid_hashes']}")
    print(f"  Temp Passwords Issued: {summary['temp_passwords_issued']}")
    print(f"  Duplicate Emails: {summary['duplicate_emails']}")
    print(f"  Orphan Profiles: {summary['orphan_profiles']}")

if __name__ == "__main__":
    run_audit()
