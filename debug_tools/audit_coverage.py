
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, Department
from accounts.models import User, OfficerProfile, Location

def audit_coverage():
    print("--- COVERAGE AUDIT ---")
    
    # 1. Analyze Issue Locations
    issues = Issue.objects.all()
    loc_depts = set()
    for iss in issues:
        loc_depts.add((iss.district, iss.taluka, iss.village, iss.city, iss.zone, iss.ward, iss.department_id))
    
    print(f"Total unique (Location, Department) pairs in existing issues: {len(loc_depts)}")

    # 2. Target Locations
    target_districts = ["Pune", "Ahmednagar"]
    target_talukas = ["Parner", "Shrigonda", "Haveli"] # Haveli is often Pune's taluka

    # 3. Analyze Officer Coverage
    depts = list(Department.objects.all())
    dept_ids = [d.id for d in depts]
    
    officers = OfficerProfile.objects.filter(is_active=True, user__is_active=True).select_related('department', 'user')
    
    coverage = {} # (DeptID, Level, Name) -> count
    for off in officers:
        # Determine jurisdiction name based on level
        name = ""
        if off.level == 'village': name = off.village
        elif off.level == 'taluka': name = off.taluka
        elif off.level == 'district': name = off.district
        elif off.level == 'city': name = off.city
        elif off.level == 'zone': name = off.zone
        elif off.level == 'ward': name = off.ward
        
        key = (off.department_id, off.level, name.lower().strip())
        coverage[key] = coverage.get(key, 0) + 1

    # 4. Summary for Target Talukas
    summary = []
    for tal_name in ["Parner", "Shrigonda"]:
        for dept in depts:
            has_taluka_officer = coverage.get((dept.id, 'taluka', tal_name.lower()), 0) > 0
            summary.append({
                "taluka": tal_name,
                "dept": dept.name,
                "has_officer": has_taluka_officer
            })

    # 5. Missing Coverage Report
    # We want at least one district officer for each dept in Pune and Ahmednagar
    # And at least one taluka officer for Parner and Shrigonda
    
    missing = []
    for dist in ["Pune", "Ahmednagar"]:
        for dept in depts:
            if coverage.get((dept.id, 'district', dist.lower()), 0) == 0:
                missing.append({"type": "district", "name": dist, "dept": dept.name, "dept_id": dept.id})

    for tal in ["Parner", "Shrigonda"]:
        # Parner/Shrigonda are in Ahmednagar
        for dept in depts:
            if coverage.get((dept.id, 'taluka', tal.lower()), 0) == 0:
                missing.append({"type": "taluka", "name": tal, "dept": dept.name, "dept_id": dept.id, "district": "Ahmednagar"})

    print(f"Missing District Level Coverage: {len([m for m in missing if m['type'] == 'district'])}")
    print(f"Missing Taluka Level Coverage: {len([m for m in missing if m['type'] == 'taluka'])}")
    
    # Check for specific village "Padali Ranjangaon" (it's in Parner)
    v_match = coverage.get((depts[0].id, 'village', 'padali ranjangaon'), 0)
    print(f"Sample village 'Padali Ranjangaon' coverage for dept {depts[0].name}: {v_match}")

    # Output detailed missing list to a file for the next step
    with open('missing_coverage.json', 'w') as f:
        json.dump(missing, f, indent=2)

if __name__ == "__main__":
    audit_coverage()
