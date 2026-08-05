import random
import csv
from django.core.management.base import BaseCommand
from django.db import transaction, models
from accounts.models import Location, OfficerProfile, Department, User

class Command(BaseCommand):
    help = "Normalize departments and apply realistic Maharashtra governance staffing policies."

    # 1. CANONICAL DEPARTMENT MAPPING
    DEPARTMENT_MAPPING = {
        "Road": "Public Works Department (PWD)",
        "Public Works": "Public Works Department (PWD)",
        "Water": "Water Supply",
        "Electric": "Electrical",
        "Electricity": "Electrical",
        "Sanitation": "Solid Waste Management",
        "Test Dept": "General",
        "Other Dept": "General",
    }

    # 2. STAFFING POLICIES
    RURAL_POLICIES = {
        "Rural Development": {"ratio": 50, "level": OfficerProfile.Level.VILLAGE, "designation": "Gram Sevak"},
        "Water Supply": {"ratio": 100, "level": OfficerProfile.Level.VILLAGE, "designation": "Water Inspector"},
        "Solid Waste Management": {"ratio": 150, "level": OfficerProfile.Level.VILLAGE, "designation": "Sanitary Inspector"},
        "Public Works Department (PWD)": {"ratio": 0, "fixed_per_taluka": 1, "level": OfficerProfile.Level.TALUKA, "designation": "Junior Engineer"},
    }

    URBAN_POLICIES = {
        "General": {"fixed_per_ward": 1, "level": OfficerProfile.Level.WARD, "designation": "Ward OfficerProfile"},
        "Solid Waste Management": {"fixed_per_ward": 1, "level": OfficerProfile.Level.WARD, "designation": "Health Inspector"},
        "Electrical": {"fixed_per_zone": 1, "level": OfficerProfile.Level.ZONE, "designation": "Executive Engineer (Elec)"},
    }

    def add_arguments(self, parser):
        parser.add_argument('--generate', action='store_true', help='Actually generate the required officers')
        parser.add_argument('--dry-run', action='store_true', help='Print gap analysis without making changes')

    def handle(self, *args, **options):
        self.stdout.write("="*60)
        self.stdout.write("MAHARASHTRA GOVERNANCE STAFFING ENGINE")
        self.stdout.write("="*60)

        # STEP 1: NORMALIZE DEPARTMENTS
        self.normalize_departments()

        # STEP 2: AUDIT & GENERATE
        self.audit_and_staff(generate=options['generate'])

    def normalize_departments(self):
        self.stdout.write("\n[STEP 1] Normalizing Departments...")
        with transaction.atomic():
            for old_name, new_name in self.DEPARTMENT_MAPPING.items():
                old_dept = Department.objects.filter(name=old_name).first()
                if not old_dept:
                    continue
                
                new_dept, _ = Department.objects.get_or_create(name=new_name)
                
                # Reassign Officers
                off_count = OfficerProfile.objects.filter(department=old_dept).update(department=new_dept)
                
                # Reassign Issues
                from issues.models import Issue
                iss_count = Issue.objects.filter(department=old_dept).update(department=new_dept)
                
                if off_count > 0 or iss_count > 0:
                    self.stdout.write(f"  Merged '{old_name}' -> '{new_name}' ({off_count} officers, {iss_count} issues)")
                
                # Delete old dept if it's not the same as new
                if old_dept.id != new_dept.id:
                    old_dept.delete()
            
            # Ensure Level is set correctly for canonical depts
            Department.objects.filter(name="Rural Development").update(level="village")
            Department.objects.filter(name="Water Supply").update(level="village")
            Department.objects.filter(name="Solid Waste Management").update(level="village")
            Department.objects.filter(name="Public Works Department (PWD)").update(level="taluka")
            Department.objects.filter(name="General").update(level="ward")

    def audit_and_staff(self, generate=False):
        self.stdout.write("\n[STEP 2] Auditing Coverage Gaps & Staffing Readiness...")
        
        districts = Location.objects.filter(type=Location.Type.DISTRICT).order_by('name')
        
        # Load all officers into a lookup cache
        all_officers = OfficerProfile.objects.all().select_related('department', 'location')
        # (loc_id, dept_name, level) -> list of officers
        officer_cache = {}
        for off in all_officers:
            key = (off.location_id, off.department.name, off.level)
            if key not in officer_cache: officer_cache[key] = []
            officer_cache[key].append(off)

        summary = []
        total_needed = 0
        total_created = 0

        for dist in districts:
            dist_needed = 0
            dist_current = 0
            
            # RURAL AUDIT
            talukas = dist.children.filter(type=Location.Type.TALUKA)
            for tal in talukas:
                village_count = tal.children.filter(type=Location.Type.VILLAGE).count()
                
                for dept_name, policy in self.RURAL_POLICIES.items():
                    needed = 0
                    if "ratio" in policy and policy["ratio"] > 0:
                        needed = max(1, village_count // policy["ratio"])
                    elif "fixed_per_taluka" in policy:
                        needed = policy["fixed_per_taluka"]
                    
                    current_key = (tal.id, dept_name, policy["level"])
                    current = len(officer_cache.get(current_key, []))
                    
                    gap = max(0, needed - current)
                    dist_needed += gap
                    dist_current += current
                    
                    if generate and gap > 0:
                        self.create_officers(tal, dept_name, policy["level"], policy["designation"], gap)
                        total_created += gap
                        if total_created % 50 == 0:
                            self.stdout.write(f"  ... Still staffing ({total_created} created)")

            # URBAN AUDIT
            cities = dist.children.filter(type=Location.Type.CITY)
            for city in cities:
                zones = city.children.filter(type=Location.Type.ZONE)
                for zone in zones:
                    wards = zone.children.filter(type=Location.Type.WARD)
                    for ward in wards:
                        for dept_name, policy in self.URBAN_POLICIES.items():
                            needed = 0
                            target_loc = None
                            if "fixed_per_ward" in policy:
                                needed = policy["fixed_per_ward"]
                                target_loc = ward
                            elif "fixed_per_zone" in policy:
                                needed = policy["fixed_per_zone"]
                                target_loc = zone
                            
                            if not target_loc: continue
                            
                            current_key = (target_loc.id, dept_name, policy["level"])
                            current = len(officer_cache.get(current_key, []))
                            
                            gap = max(0, needed - current)
                            dist_needed += gap
                            dist_current += current
                            
                            if generate and gap > 0:
                                self.create_officers(target_loc, dept_name, policy["level"], policy["designation"], gap)
                                total_created += gap
                                if total_created % 100 == 0:
                                    self.stdout.write(f"  ... Still staffing ({total_created} created)")

            # CALC SCORES
            readiness = (dist_current / (dist_current + dist_needed)) * 100 if (dist_current + dist_needed) > 0 else 100
            total_needed += dist_needed
            
            summary.append({
                "district": dist.name,
                "current": dist_current,
                "gap": dist_needed,
                "readiness": readiness
            })

        if generate:
            self.stdout.write(self.style.SUCCESS(f"\nCreated {total_created} officers realistically."))

        # PRINT SUMMARY
        self.stdout.write("\n" + "-"*60)
        self.stdout.write(f"{'District':20} | {'Current':8} | {'Gap':5} | {'Readiness':10}")
        self.stdout.write("-"*60)
        for s in summary:
            status = "STABLE" if s['readiness'] > 80 else "CRITICAL" if s['readiness'] < 20 else "WEAK"
            self.stdout.write(f"{s['district']:20} | {s['current']:8} | {s['gap']:5} | {s['readiness']:9.1f}% ({status})")
        
        self.stdout.write("-"*60)
        self.stdout.write(f"TOTAL SYSTEM GAP: {total_needed} officers needed.")
        
        if not generate and total_needed > 0:
            self.stdout.write(self.style.WARNING("\nRun with --generate to fill these gaps realistically."))

    def create_officers(self, location, dept_name, level, designation, count):
        # Realistic Maharashtrian naming components
        fnames = ["Abhijeet", "Rajendra", "Sandeep", "Anjali", "Snehal", "Vijay", "Sanjay", "Manisha", "Vikas", "Sachin", "Rahul", "Sunil", "Prakash", "Anita", "Deepak", "Rajesh", "Pooja", "Kiran"]
        lnames = ["Pawar", "Kulkarni", "Jadhav", "Deshmukh", "Patil", "Shinde", "More", "Gaikwad", "Chavan", "Kadam", "Joshi", "Thorat", "Sawant", "Ghorpade", "Bhonsle"]
        
        dept = Department.objects.get(name=dept_name)
        
        for _ in range(count):
            fn = random.choice(fnames)
            ln = random.choice(lnames)
            full_name = f"{fn} {ln}"
            # Unique suffix to avoid collisions
            suffix = random.randint(1000, 99999)
            uname = f"{fn.lower()}.{ln.lower()}.{suffix}"
            email = f"{uname}@mahagov.in"
            
            user = User.objects.create_user(
                username=uname, email=email, password="Civica@123",
                full_name=full_name, role=User.Role.OFFICER, is_approved=True
            )
            
            OfficerProfile.objects.create(
                user=user, department=dept, location=location,
                full_name=full_name, designation=designation,
                level=level, phone=f"+91{random.randint(7000000000, 9999999999)}",
                is_active=True
            )
