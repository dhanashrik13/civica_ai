import random
import re
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from accounts.models import User, OfficerProfile, Department, Location
from issues.models import Issue

import requests
from io import BytesIO
from django.core.files.base import ContentFile

class Command(BaseCommand):
    help = "Seed the database with realistic Issue data (50 per department)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing issues before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing issues...")
            Issue.objects.all().delete()

        departments = Department.objects.all()
        citizens = list(User.objects.filter(role=User.Role.CITIZEN))
        officers = list(OfficerProfile.objects.all())

        if not citizens:
            self.stdout.write(self.style.ERROR("No citizens found in DB. Please seed users first."))
            return
        if not departments:
            self.stdout.write(self.style.ERROR("No departments found in DB."))
            return

        # Realistic data mapping
        DEPT_DATA = {
            "Road": {
                "category": Issue.Category.POTHOLE,
                "titles": ["Large Pothole near Main Square", "Broken Road Surface", "Crack on Highway Edge", "Sunken Road Segment"],
                "descriptions": ["A deep pothole is causing traffic delays and risks for two-wheelers.", "The asphalt has completely worn away near the bus stop."]
            },
            "Public Works": {
                "category": Issue.Category.ROAD_DAMAGE,
                "titles": ["Damaged Pavement", "Illegal Road Cutting", "Missing Manhole Cover on Road"],
                "descriptions": ["A section of the road was cut for cabling but never repaired.", "The pavement stones are loose and dangerous for pedestrians."]
            },
            "Water": {
                "category": Issue.Category.WATER_LEAKAGE,
                "titles": ["Main Pipeline Burst", "Water Leaking from Valve", "Underground Pipe Leakage", "Water Tank Overflow"],
                "descriptions": ["Drinking water is being wasted for hours due to a pipeline burst.", "Severe leakage observed near the society entrance."]
            },
            "Sanitation": {
                "category": Issue.Category.GARBAGE,
                "titles": ["Garbage Pile on Street", "Overflowing Trash Bin", "Illegal Waste Dumping", "Nauseating Smell from Dumpster"],
                "descriptions": ["Waste hasn't been collected for three days, causing health concerns.", "Illegal dumping of construction waste in a residential area."]
            },
            "Electricity": {
                "category": Issue.Category.STREET_LIGHT,
                "titles": ["Flickering Street Light", "Broken Lamp Post", "Street Completely Dark at Night"],
                "descriptions": ["The street light has been off for a week, making it unsafe after dark.", "Exposed wires found at the base of the lamp post."]
            },
            "Electric": {
                "category": Issue.Category.STREET_LIGHT,
                "titles": ["Short Circuit in Pole", "Dark Alleyway", "Inoperative LED Street Light"],
                "descriptions": ["The high mast light in the park is not working.", "Wires are sparking during the rain."]
            },
            "Drainage": {
                "category": Issue.Category.DRAINAGE,
                "titles": ["Blocked Sewer Line", "Sewage Overflow on Road", "Stagnant Water in Drain", "Broken Drainage Pipe"],
                "descriptions": ["The drainage is completely blocked, causing foul odor in the area.", "Sewage water is entering the ground floor of nearby buildings."]
            }
        }

        # Generic fallbacks
        FALLBACK_DATA = {
            "titles": ["General Issue Reported", "Maintenance Required", "Service Request"],
            "descriptions": ["A request for inspection and maintenance in this area.", "The infrastructure needs urgent attention from the department."]
        }

        # Realistic data mapping with strict category-dept alignment
        DEPT_MAP = {
            "Road": {"cat": Issue.Category.POTHOLE, "key": "Road"},
            "Public Works": {"cat": Issue.Category.ROAD_DAMAGE, "key": "Public Works"},
            "Water": {"cat": Issue.Category.WATER_LEAKAGE, "key": "Water"},
            "Sanitation": {"cat": Issue.Category.GARBAGE, "key": "Sanitation"},
            "Electricity": {"cat": Issue.Category.STREET_LIGHT, "key": "Electricity"},
            "Electric": {"cat": Issue.Category.STREET_LIGHT, "key": "Electric"},
            "Drainage": {"cat": Issue.Category.DRAINAGE, "key": "Drainage"}
        }

        total_created = 0
        total_resolved = 0
        total_assigned = 0

        with transaction.atomic():
            for dept in departments:
                self.stdout.write(f"Seeding department: {dept.name}...")
                
                # Get relevant data for this department or fallback
                data = None
                for name_key, mapping in DEPT_MAP.items():
                    if name_key.lower() in dept.name.lower():
                        data = DEPT_DATA.get(mapping["key"])
                        category = mapping["cat"]
                        break
                
                if not data:
                    data = FALLBACK_DATA
                    # Ensure we don't pick DRAINAGE for non-drainage depts
                    category = Issue.Category.POTHOLE if "Drainage" not in dept.name else Issue.Category.DRAINAGE

                resolved_limit = random.randint(5, 15)
                resolved_count_dept = 0
                
                # Get officers for this department strictly
                dept_officers = [o for o in officers if o.department_id == dept.id]

                for i in range(50):
                    status = Issue.Status.PENDING
                    resolved_at = None
                    assigned_to = None
                    location = None
                    
                    # Only attempt assignment/resolution if officers exist for this department
                    if dept_officers:
                        if resolved_count_dept < resolved_limit:
                            status = Issue.Status.RESOLVED
                            resolved_at = timezone.now() - timezone.timedelta(days=random.randint(1, 10))
                            resolved_count_dept += 1
                            total_resolved += 1
                            assigned_to = random.choice(dept_officers)
                            location = assigned_to.location # Match location to pass validation
                        else:
                            # For non-resolved, randomly assign
                            if random.choice([True, False]):
                                status = Issue.Status.ASSIGNED
                                assigned_to = random.choice(dept_officers)
                                location = assigned_to.location # Match location
                                total_assigned += 1
                    
                    # DYNAMIC IMAGE GENERATION
                    raw_title = random.choice(data['titles'])
                    title = f"{raw_title} #{i+1}"
                    
                    # 1. Keywords extraction (Lowercase, No special characters, Space -> Comma)
                    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', raw_title).lower().strip()
                    keywords = clean_title.replace(' ', ',')
                    
                    # 2. Final URL with fallback
                    if keywords:
                        image_url = f"https://source.unsplash.com/400x300/?{keywords}"
                    else:
                        image_url = "https://picsum.photos/400/300"
                    
                    # Create the issue
                    photo_file = None
                    try:
                        resp = requests.get(image_url, timeout=5)
                        if resp.status_code == 200:
                            photo_file = ContentFile(resp.content, name=f"issue_{total_created}.jpg")
                    except Exception as e:
                        self.stdout.write(f"Warning: Could not download image {image_url}: {e}")

                    Issue.objects.create(
                        title=title,
                        description=random.choice(data['descriptions']),
                        category=category,
                        priority=random.choice(Issue.Priority.choices)[0],
                        department=dept,
                        location=location,
                        location_source="manual_city",
                        latitude=18.5204 + random.uniform(-0.1, 0.1),
                        longitude=73.8567 + random.uniform(-0.1, 0.1),
                        photo1=photo_file,
                        status=status,
                        reported_by=random.choice(citizens),
                        assigned_to=assigned_to,
                        resolved_at=resolved_at,
                        created_at=timezone.now() - timezone.timedelta(days=random.randint(0, 30))
                    )
                    total_created += 1

        self.stdout.write(self.style.SUCCESS(f"\nSeeding complete!"))
        self.stdout.write(f"Total issues created: {total_created}")
        self.stdout.write(f"Total resolved: {total_resolved}")
        self.stdout.write(f"Total assigned (excluding resolved): {total_assigned}")

if __name__ == "__main__":
    pass
