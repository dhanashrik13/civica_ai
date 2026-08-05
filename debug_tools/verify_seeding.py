
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue, Department
from accounts.models import User, OfficerProfile, Location
from issues.services import auto_assign_issue
from issues.tasks import enrich_issue_context

def verify_seeding():
    print("--- VERIFYING AUTO ASSIGNMENT ---")
    
    # 1. Test Road issue in Pune village
    # 2. Test Water issue in Parner
    # 3. Test Sanitation issue in Shrigonda

    citizen = User.objects.filter(role=User.Role.CITIZEN).first()
    
    test_cases = [
        {
            "title": "Pune Road Test",
            "category": Issue.Category.POTHOLE,
            "district": "Pune",
            "taluka": "Haveli",
            "village": "Wagholi",
            "expected_dept": "Public Works Department (PWD)"
        },
        {
            "title": "Parner Water Test",
            "category": Issue.Category.WATER_SUPPLY,
            "district": "Ahmednagar",
            "taluka": "Parner",
            "village": "Padali Ranjangaon",
            "expected_dept": "Water Supply Department"
        },
        {
            "title": "Shrigonda Sanitation Test",
            "category": Issue.Category.SANITATION,
            "district": "Ahmednagar",
            "taluka": "Shrigonda",
            "village": "Unknown Village",
            "expected_dept": "Sanitation Department"
        }
    ]

    results = []

    for tc in test_cases:
        # Get or create location
        dist_loc, _ = Location.objects.get_or_create(name=tc['district'], type='district')
        tal_loc, _ = Location.objects.get_or_create(name=tc['taluka'], type='taluka', parent=dist_loc)
        vil_loc, _ = Location.objects.get_or_create(name=tc['village'], type='village', parent=tal_loc)

        issue = Issue.objects.create(
            title=tc['title'],
            category=tc['category'],
            reported_by=citizen,
            location=vil_loc,
            village=tc['village'],
            taluka=tc['taluka'],
            district=tc['district']
        )
        
        # Trigger enrichment and assignment
        enrich_issue_context(issue.id)
        
        issue.refresh_from_db()
        
        assigned_officer = issue.assigned_to.user.username if issue.assigned_to else "Not Assigned"
        status = "SUCCESS" if issue.assigned_to else "FAILED"
        
        results.append({
            "Test Issue": tc['title'],
            "Expected Department": tc['expected_dept'],
            "Assigned Officer": assigned_officer,
            "Result": status
        })
        
        print(f"Test: {tc['title']} | Dept: {tc['expected_dept']} | Assigned: {assigned_officer} | Result: {status}")

    with open('verification_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    verify_seeding()
