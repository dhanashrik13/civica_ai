
import os
import django
import json
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, Department
from accounts.models import User, OfficerProfile, Location
from django.db import transaction

def seed_officers():
    print("--- SEEDING MISSING OFFICERS ---")
    
    with open('missing_coverage.json', 'r') as f:
        missing = json.load(f)

    depts = {d.id: d for d in Department.objects.all()}
    
    created_officers = []
    reused_officers = []

    # Map for location lookup
    loc_map = {} # (name.lower(), type) -> Location

    with transaction.atomic():
        for m in missing:
            dept = depts.get(m['dept_id'])
            if not dept: continue
            
            level = m['type']
            loc_name = m['name']
            
            # Find or create Location object
            loc_key = (loc_name.lower(), level)
            if loc_key not in loc_map:
                loc = Location.objects.filter(name__iexact=loc_name, type=level).first()
                if not loc:
                    # Try to find parent if it's a taluka
                    parent = None
                    if level == 'taluka':
                        parent = Location.objects.filter(name__iexact=m.get('district', 'Ahmednagar'), type='district').first()
                    loc = Location.objects.create(name=loc_name, type=level, parent=parent)
                loc_map[loc_key] = loc
            
            loc = loc_map[loc_key]

            # Unique username/email
            sanitized_name = loc_name.lower().replace(" ", "_")
            sanitized_dept = dept.name.lower().split("(")[0].strip().replace(" ", "_").replace("&", "and")
            username = f"{sanitized_dept}_{sanitized_name}_{level[:2]}"
            
            # Check if username exists
            if User.objects.filter(username=username).exists():
                # Try to append a number if it exists
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

            email = f"{username}@mahagov.in"

            # Create User
            user = User.objects.create_user(
                username=username,
                email=email,
                password="Civica@123",
                role=User.Role.OFFICER,
                is_approved=True
            )
            
            # Create Profile
            # Set geo fields based on level
            profile_data = {
                'user': user,
                'department': dept,
                'location': loc,
                'level': level,
                'is_active': True,
                'full_name': f"{dept.name} Officer ({loc_name})",
            }
            
            if level == 'district':
                profile_data['district'] = loc_name
            elif level == 'taluka':
                profile_data['taluka'] = loc_name
                profile_data['district'] = m.get('district', 'Ahmednagar')
            
            OfficerProfile.objects.create(**profile_data)
            
            created_officers.append({
                "Username": username,
                "Department": dept.name,
                "Location": loc_name,
                "Governance Scope": level
            })

    # Output results for summary tables
    results = {
        "created": created_officers,
        "reused": reused_officers
    }
    with open('seeding_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Successfully created {len(created_officers)} officers.")

if __name__ == "__main__":
    seed_officers()
