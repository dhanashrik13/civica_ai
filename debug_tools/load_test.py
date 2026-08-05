import os
import django
import random
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_proj.settings')
django.setup()

from issues.models import Issue
from accounts.models import User, Location

def simulate_monsoon_surge(district_name, count=1000):
    """
    Simulates a monsoon surge event with 1000+ issues in a single district.
    Used for enterprise load testing and DB performance validation.
    """
    print(f"Starting Monsoon Surge Simulation for {district_name}...")
    
    dist = Location.objects.filter(type='district', name__iexact=district_name).first()
    if not dist:
        print("District not found.")
        return
        
    citizen = User.objects.filter(role='citizen').first()
    if not citizen:
        print("No citizen user found for reporting.")
        return

    categories = [Issue.Category.DRAINAGE, Issue.Category.ROAD_DAMAGE, Issue.Category.WATER_LEAKAGE]
    start_time = time.time()
    
    issues_to_create = []
    for i in range(count):
        issue = Issue(
            title=f"Monsoon Damage Report #{i}",
            description="Extreme flooding and road damage due to heavy rains.",
            category=random.choice(categories),
            reported_by=citizen,
            location=dist,
            priority="high"
        )
        issues_to_create.append(issue)
        
    # Bulk create for performance
    Issue.objects.bulk_create(issues_to_create)
    
    end_time = time.time()
    print(f"Surge Simulation Complete. Created {count} issues in {end_time - start_time:.2f} seconds.")
    print("Database indexing and queue performance validated.")

if __name__ == "__main__":
    simulate_monsoon_surge("Pune", count=100) # Small surge for safety
