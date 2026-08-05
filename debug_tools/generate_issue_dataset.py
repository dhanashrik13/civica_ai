import os
import django
import random
from datetime import timedelta
from django.utils import timezone
from django.core.files.base import ContentFile

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import User, Location, IssueImage
from issues.models import Issue, Department

def generate_small_image(name):
    """Generates a tiny valid PNG file."""
    # 1x1 pixel PNG (red)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xdcD\x05\xe8\x00\x00\x00\x00IEND\xaeB`\x82'
    return ContentFile(png_data, name=name)

def generate_dataset():
    print("Starting data generation...")
    
    citizens = list(User.objects.filter(role='citizen'))
    if not citizens:
        print("No citizens found! Creating a dummy one.")
        citizen = User.objects.create_user(username="dummy_citizen", password="password123", role="citizen")
        citizens = [citizen]
    
    districts = {
        "Ahilyanagar": ["Parner", "Shrigonda"],
        "Pune": ["Pune City", "Haveli", "Shirur", "Pimpri-Chinchwad"]
    }

    categories = [
        ("pothole", "Pothole"),
        ("road_damage", "Road Damage"),
        ("water_leakage", "Water Leakage"),
        ("street_light", "Street Light"),
        ("garbage", "Garbage"),
        ("drainage", "Drainage"),
    ]
    
    # Extended categories as per requirement, mapped to existing choices if possible
    # My grep showed: POTHOLE, ROAD_DAMAGE, WATER_LEAKAGE, STREET_LIGHT, GARBAGE, DRAINAGE
    # I should check if there are more in the model.
    
    issue_templates = [
        {"title": "Large pothole on main road", "desc": "Big pothole near the bus stand, causing traffic and risks for bikers.", "cat": "pothole"},
        {"title": "Garbage pile not cleared", "desc": "Garbage has not been collected for 4 days. Strong smell in the area.", "cat": "garbage"},
        {"title": "Water pipe leakage", "desc": "Main water line is leaking near the ZP school. Lot of water wastage.", "cat": "water_leakage"},
        {"title": "Street lights not working", "desc": "All street lights on the colony road are off since yesterday night.", "cat": "street_light"},
        {"title": "Open drainage manhole", "desc": "The drainage cover is broken near the market. Very dangerous at night.", "cat": "drainage"},
        {"title": "Broken road after rain", "desc": "The internal road is completely washed away after heavy rains.", "cat": "road_damage"},
        {"title": "Sewage overflow in ward 4", "desc": "Drainage water is coming out on the road. Please fix urgently.", "cat": "drainage"},
        {"title": "Illegal dumping in open plot", "desc": "People are throwing construction waste in the empty plot near my house.", "cat": "garbage"},
        {"title": "Street light pole leaning", "desc": "One electricity pole is leaning dangerously towards the road.", "cat": "street_light"},
        {"title": "Pipe line burst", "desc": "Water pipeline burst during road work. Road is flooded.", "cat": "water_leakage"},
        {"title": "Public toilet damage", "desc": "The doors of the public toilet in our area are broken.", "cat": "drainage"}, # Mapping to drainage or others
        {"title": "Tree collapse blocking road", "desc": "A large tree fell down near the square. Road is blocked.", "cat": "road_damage"},
    ]

    marathi_english_templates = [
        {"title": "Khadda on road", "desc": "Road var khup motha khadda ahe. Accident honyachi shakyata ahe.", "cat": "pothole"},
        {"title": "Pani गळती", "desc": "Pipe line footli ahe, pani rastyavar yetoy.", "cat": "water_leakage"},
        {"title": "Kachra samasya", "desc": "Wadi madhe kachra gadi yet nahi 3 divas zale.", "cat": "garbage"},
        {"title": "Light band ahe", "desc": "Gallitli light lagat nahi, khup andhar asto.", "cat": "street_light"},
        {"title": "Gatar saaf kara", "desc": "Gatar block zale ahe, pani baher yetoy.", "cat": "drainage"},
    ]

    all_templates = issue_templates * 5 + marathi_english_templates * 5
    random.shuffle(all_templates)

    total_created = 0
    
    # Get departments to avoid null if possible
    depts = list(Department.objects.all())

    for i in range(105):
        template = random.choice(all_templates)
        district = random.choice(list(districts.keys()))
        taluka = random.choice(districts[district])
        
        reporter = random.choice(citizens)
        
        # Random status
        status = random.choice(["pending", "assigned", "resolved", "pending", "assigned"]) # weight towards pending/assigned
        
        # Priority
        priority = random.choice(["low", "medium", "high", "emergency"])
        
        # Random Village/Ward
        if taluka in ["Pune City", "Pimpri-Chinchwad"]:
            village = None
            ward = f"Ward {random.randint(1, 15)}"
            city = taluka
        else:
            village = f"Village {random.randint(1, 50)}"
            ward = None
            city = None

        # Fetch Location object if possible
        loc_obj = Location.objects.filter(name=taluka, type="taluka").first()
        if not loc_obj and city:
            loc_obj = Location.objects.filter(name=city, type="city").first()

        created_at = timezone.now() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        
        issue = Issue.objects.create(
            title=f"{template['title']} - {i+1}",
            description=f"{template['desc']} Reported from {taluka}.",
            category=template['cat'],
            priority=priority,
            status=status,
            reported_by=reporter,
            district=district,
            taluka=taluka,
            village=village,
            ward=ward,
            city=city,
            latitude=random.uniform(18.0, 19.5),
            longitude=random.uniform(73.5, 75.0),
            location=loc_obj,
            created_at=created_at,
            updated_at=created_at + timedelta(hours=random.randint(1, 24))
        )
        
        # Override auto_now_add
        Issue.objects.filter(id=issue.id).update(created_at=created_at)

        # Add images
        num_images = random.randint(1, 3)
        for j in range(num_images):
            img_name = f"issue_{issue.id}_{j}.png"
            IssueImage.objects.create(
                issue=issue,
                image=generate_small_image(img_name)
            )
            
        total_created += 1
        if total_created % 10 == 0:
            print(f"Created {total_created} issues...")

    print(f"Successfully created {total_created} issues.")
    return total_created

if __name__ == "__main__":
    generate_dataset()
