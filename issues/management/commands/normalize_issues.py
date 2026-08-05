import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model
from accounts.models import Department, OfficerProfile, Location
from issues.models import Issue

User = get_user_model()

class Command(BaseCommand):
    help = "Clean image-less issues and normalize database with valid, assigned data."

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database normalization...")
        
        # Mapping Category -> [Titles] -> Department Name
        DATA_MAP = {
            Issue.Category.POTHOLE: {
                "titles": ["Deep pothole on main road", "Hazardous pothole near school", "Series of potholes after rain"],
                "dept": "Road"
            },
            Issue.Category.ROAD_DAMAGE: {
                "titles": ["Cracked pavement", "Edge drop-off", "Sunken road surface"],
                "dept": "Public Works"
            },
            Issue.Category.WATER_LEAKAGE: {
                "titles": ["Main pipe burst", "Leaking hydrant", "Water wastage from valve"],
                "dept": "Water"
            },
            Issue.Category.STREET_LIGHT: {
                "titles": ["Street light not working", "Flickering street lamp", "Entire block dark"],
                "dept": "Electricity"
            },
            Issue.Category.GARBAGE: {
                "titles": ["Overflowing bin", "Illegal dumping", "Garbage not collected"],
                "dept": "Sanitation"
            },
            Issue.Category.DRAINAGE: {
                "titles": ["Blocked drain", "Sewage overflow", "Broken drain cover"],
                "dept": "Drainage"
            }
        }

        with transaction.atomic():
            # 1. Delete invalid issues (no photos)
            invalid_issues = Issue.objects.filter(
                (Q(photo1='') | Q(photo1__isnull=True)) &
                (Q(photo2='') | Q(photo2__isnull=True)) &
                (Q(photo3='') | Q(photo3__isnull=True))
            )
            deleted_count = invalid_issues.count()
            invalid_issues.delete()
            self.stdout.write(f"Deleted {deleted_count} image-less issues.")

            # 2. Preparation
            citizens = list(User.objects.filter(role=User.Role.CITIZEN))
            if not citizens:
                self.stdout.write("Creating default citizen...")
                c = User.objects.create_user(username="citizen_default", password="password123", role=User.Role.CITIZEN, full_name="Default Citizen")
                citizens = [c]

            districts = list(Location.objects.filter(type=Location.Type.DISTRICT))
            if not districts:
                districts = [Location.objects.create(name="Pune", type=Location.Type.DISTRICT)]

            officers_created = 0
            issues_created = 0

            # 3. Create Valid Issues
            for category, info in DATA_MAP.items():
                dept, _ = Department.objects.get_or_create(name=info["dept"])
                
                for title in info["titles"]:
                    location_name = random.choice(["Shivajinagar", "Kothrud", "Baner", "Hinjewadi"])
                    district = random.choice(districts)
                    
                    # Prevent duplicates
                    if Issue.objects.filter(title=title, location=location_name).exists():
                        continue

                    status = random.choice([Issue.Status.PENDING, Issue.Status.ASSIGNED, Issue.Status.RESOLVED])
                    
                    # Ensure OfficerProfile exists for Dept + District
                    officer = OfficerProfile.objects.filter(department=dept, district=district.name).first()
                    if not officer and status in [Issue.Status.ASSIGNED, Issue.Status.RESOLVED]:
                        # Create OfficerProfile User
                        off_username = f"off_{dept.name.lower()}_{district.name.lower()}"
                        off_user, u_created = User.objects.get_or_create(
                            username=off_username,
                            defaults={
                                "role": User.Role.OFFICER,
                                "full_name": f"{dept.name} OfficerProfile ({district.name})",
                                "is_approved": True
                            }
                        )
                        if u_created:
                            off_user.set_password("password123")
                            off_user.save()
                        
                        officer, o_created = OfficerProfile.objects.get_or_create(
                            user=off_user,
                            defaults={
                                "department": dept,
                                "location": district,
                                "district": district.name,
                                "level": "district"
                            }
                        )
                        if o_created:
                            officers_created += 1

                    # Create Issue
                    issue = Issue.objects.create(
                        title=title,
                        description=f"Automated report for {title} in {location_name}.",
                        category=category,
                        priority=random.choice(Issue.Priority.choices)[0],
                        department=dept,
                        location=location_name,
                        district=district.name,
                        latitude=random.uniform(18.4, 18.6),
                        longitude=random.uniform(73.7, 73.9),
                        status=status,
                        reported_by=random.choice(citizens),
                        assigned_to=officer if status in [Issue.Status.ASSIGNED, Issue.Status.RESOLVED] else None
                    )
                    
                    # Manually add a dummy photo reference to make it "valid"
                    issue.photo1 = "issue_photos/sample.jpg"
                    issue.save()
                    issues_created += 1

            final_count = Issue.objects.count()
            
            self.stdout.write(self.style.SUCCESS(f"Normalization complete!"))
            self.stdout.write(f"- Issues Deleted: {deleted_count}")
            self.stdout.write(f"- Issues Created: {issues_created}")
            self.stdout.write(f"- Officers Created: {officers_created}")
            self.stdout.write(f"- Final Issue Count: {final_count}")
