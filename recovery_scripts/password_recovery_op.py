import os
import django
import sys
import csv
import random
import string
from django.db import transaction
from django.contrib.auth.hashers import identify_hasher, is_password_usable, make_password
from django.utils import timezone

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, CitizenProfile, OfficerProfile, AdminProfile
from issues.models import Issue

def generate_temp_password(username):
    """Generates a password in format Gov@<Username><4RandomDigits>"""
    digits = ''.join(random.choices(string.digits, k=4))
    # Remove spaces and normalize username if necessary, though it should be valid
    clean_username = str(username).replace(" ", "")
    return f"Gov@{clean_username}{digits}"

def validate_hash(pwd_hash):
    """Safely validates the hash format and usability."""
    if not pwd_hash:
        return False
    try:
        identify_hasher(pwd_hash)
        if not is_password_usable(pwd_hash):
            return False
        return True
    except:
        return False

def run_recovery_operation():
    print("Starting STRICT PASSWORD RECOVERY & RESET OPERATION...")
    
    results = []
    summary = {
        "total_resets": 0,
        "citizens": 0,
        "officers": 0,
        "admins": 0
    }

    # Pre-calculate Issue counts for the report
    from django.db.models import Count
    citizen_issue_counts = {item['reported_by']: item['count'] for item in Issue.objects.values('reported_by').annotate(count=Count('id'))}
    officer_issue_counts = {item['assigned_to']: item['count'] for item in Issue.objects.values('assigned_to').annotate(count=Count('id'))}

    profile_sets = [
        ("Citizen", CitizenProfile.objects.all().select_related('user')),
        ("Officer", OfficerProfile.objects.all().select_related('user', 'department')),
        ("Admin", AdminProfile.objects.all().select_related('user', 'department'))
    ]

    for role_name, queryset in profile_sets:
        total = queryset.count()
        print(f"  Processing {role_name} accounts (Total: {total})...")
        count = 0
        for profile in queryset:
            count += 1
            if count % 100 == 0:
                print(f"    Processed {count}/{total} {role_name}s...")
            # ...
            # Requirements: Validate username, email, password_hash exist
            user = None
            try:
                user = profile.user
            except User.DoesNotExist:
                continue # Orphan profiles might not be targetable if we need to sync to User

            username = profile.username or user.username
            email = profile.email or user.email
            pwd_hash = profile.password_hash

            if not username or not email or not pwd_hash:
                continue

            # Check if hash is valid
            if validate_hash(pwd_hash):
                # We don't know the original password, so we generate a new one
                temp_pwd = generate_temp_password(username)
                new_hash = make_password(temp_pwd)

                try:
                    with transaction.atomic():
                        # Save to profile
                        profile.password_hash = new_hash
                        
                        # Mark password_reset_required = True (using metadata since field doesn't exist)
                        if role_name == "Citizen":
                            profile.reporting_metadata["PASSWORD_RESET_REQUIRED"] = True
                        elif role_name == "Officer":
                            profile.verified_communication_metadata["PASSWORD_RESET_REQUIRED"] = True
                        elif role_name == "Admin":
                            profile.governance_control_metadata["PASSWORD_RESET_REQUIRED"] = True
                        
                        profile.save()

                        # Also update User for consistency (as they share the same identity)
                        if user:
                            user.password = new_hash
                            user.save()

                    summary["total_resets"] += 1
                    if role_name == "Citizen": summary["citizens"] += 1
                    elif role_name == "Officer": summary["officers"] += 1
                    elif role_name == "Admin": summary["admins"] += 1

                    # Gather data for report
                    issue_count = citizen_issue_counts.get(user.id, 0) if role_name == "Citizen" else 0
                    assigned_count = officer_issue_counts.get(profile.id, 0) if role_name == "Officer" else 0
                    
                    results.append({
                        "Role": role_name,
                        "Username": username,
                        "Email": email,
                        "NEW Temporary Password": temp_pwd,
                        "Password Reset Required": "True",
                        "Citizen Issue Count": issue_count,
                        "Officer Assigned Count": assigned_count,
                        "Active Status": "Active" if profile.is_active else "Inactive"
                    })
                except Exception as e:
                    print(f"    Failed to reset {username}: {str(e)}")

    # Export CSV
    print("Exporting CSV...")
    with open("PASSWORD_RESET_REPORT.csv", "w", newline="", encoding="utf-8") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    # Export MD
    print("Exporting Markdown report...")
    with open("PASSWORD_RESET_REPORT.md", "w", encoding="utf-8") as f:
        f.write("# STRICT PASSWORD RECOVERY & RESET REPORT\n\n")
        f.write(f"**Execution Date:** {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## OPERATIONS SUMMARY\n\n")
        f.write(f"- **Total Passwords Reset:** {summary['total_resets']}\n")
        f.write(f"- **Citizens Processed:** {summary['citizens']}\n")
        f.write(f"- **Officers Processed:** {summary['officers']}\n")
        f.write(f"- **Admins Processed:** {summary['admins']}\n\n")

        f.write("## RESET LOG\n\n")
        f.write("| Role | Username | Email | NEW Temp Password | Reset Required | Issues | Assigned | Status |\n")
        f.write("|------|----------|-------|-------------------|----------------|--------|----------|--------|\n")
        for r in results:
            f.write(f"| {r['Role']} | {r['Username']} | {r['Email']} | `{r['NEW Temporary Password']}` | {r['Password Reset Required']} | {r['Citizen Issue Count']} | {r['Officer Assigned Count']} | {r['Active Status']} |\n")

    print(f"Operation complete. Reset {summary['total_resets']} accounts.")

if __name__ == "__main__":
    run_recovery_operation()
