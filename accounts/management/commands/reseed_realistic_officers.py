import random
import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from accounts.models import OfficerProfile, Department, Location

User = get_user_model()

class Command(BaseCommand):
    help = "Safely remove existing OfficerProfile test data and recreate a realistic Maharashtra Government OfficerProfile hierarchy."

    def handle(self, *args, **options):
        # 1. DELETE ONLY EXISTING OFFICER TEST DATA
        self.stdout.write("Auditing existing officer data...")
        
        # We only delete users who have the 'officer' role to avoid deleting citizens or admins.
        # However, the user also mentioned "seeded officer accounts" and "demo/test officers".
        # Most of these should have an associated OfficerProfile record.
        
        officer_users = User.objects.filter(role=User.Role.OFFICER)
        officer_user_count = officer_users.count()
        officer_record_count = OfficerProfile.objects.count()

        self.stdout.write(f"Found {officer_record_count} OfficerProfile records and {officer_user_count} User records with role='officer'.")

        with transaction.atomic():
            # Safely identify users to delete: those with role='officer'
            # We preserve citizens, admins, and dept_admins.
            
            # Delete ALL OfficerProfile profiles first. This is safe as it doesn't delete the User.
            OfficerProfile.objects.all().delete()
            
            # Now delete the Users who are specifically in the 'officer' role.
            users_to_delete_count = User.objects.filter(role=User.Role.OFFICER).count()
            User.objects.filter(role=User.Role.OFFICER).delete()

            self.stdout.write(self.style.SUCCESS(f"Deleted all legacy OfficerProfile profiles and {users_to_delete_count} User records with role='officer'."))

            # 2. ENSURE DEPARTMENTS
            departments_data = [
                ("Public Works Department (PWD)", "district"),
                ("Water Supply", "district"),
                ("Solid Waste Management", "taluka"),
                ("Sanitation", "village"),
                ("Electrical", "taluka"),
                ("Health & Sanitation", "district"),
                ("Rural Development", "district"),
            ]
            
            depts = {}
            for name, level in departments_data:
                dept, created = Department.objects.get_or_create(name=name, defaults={'level': level})
                depts[name] = dept
                if created:
                    self.stdout.write(f"Created Department: {name}")

            # 3. ENSURE LOCATIONS
            locations_data = {
                "Pune": ["Haveli", "Baramati", "Shirur", "Kothrud", "Shivajinagar", "Viman Nagar", "Baner", "Pimpri"],
                "Ahilyanagar": ["Sangamner", "Rahata", "Nagar", "Shrirampur"],
                "Nashik": ["Nashik City", "Malegaon", "Sinnar", "Niphad"],
                "Nagpur": ["Nagpur City", "Kamthi", "Katol", "Ramtek"],
                "Nanded": ["Nanded City", "Loha", "Deglur", "Mudkhed"]
            }

            loc_map = {}
            for dist_name, talukas in locations_data.items():
                dist, _ = Location.objects.get_or_create(name=dist_name, type=Location.Type.DISTRICT)
                loc_map[dist_name] = {"dist": dist, "talukas": []}
                for tal_name in talukas:
                    tal, _ = Location.objects.get_or_create(name=tal_name, type=Location.Type.TALUKA, parent=dist)
                    loc_map[dist_name]["talukas"].append(tal)

            # 4. CREATE REALISTIC OFFICERS
            first_names_male = ["Abhijeet", "Rajendra", "Sandeep", "Vijay", "Sanjay", "Prakash", "Nitin", "Rahul", "Sunil", "Manoj", "Ganesh", "Amit", "Vikas", "Sachin", "Prashant", "Anil", "Deepak", "Rajesh", "Santosh", "Suresh"]
            first_names_female = ["Anjali", "Snehal", "Pallavi", "Deepali", "Jyoti", "Sunita", "Kavita", "Vidya", "Manisha", "Varsha"]
            last_names = ["Pawar", "Kulkarni", "Jadhav", "Deshmukh", "Patil", "Shinde", "More", "Gaikwad", "Chavan", "Kadam", "Joshi", "Bhonsle", "Sawant", "Thorat", "Ghorpade"]

            officer_logins = []
            password = "Civica@123"

            # Hierarchy Levels:
            # L3 -> Administrative Heads (District)
            # L2 -> Supervisory Officers (Taluka)
            # L1 -> Field Officers (Village/Taluka)

            hierarchy_config = [
                {
                    "level": OfficerProfile.Level.DISTRICT, 
                    "designations": ["Municipal Commissioner", "CEO Zilla Parishad", "Deputy Commissioner"], 
                    "count_per_dist": 2,
                    "loc_type": "dist"
                },
                {
                    "level": OfficerProfile.Level.TALUKA, 
                    "designations": ["Executive Engineer", "Ward OfficerProfile", "Block Development OfficerProfile"], 
                    "count_per_dist": 5,
                    "loc_type": "taluka"
                },
                {
                    "level": OfficerProfile.Level.VILLAGE, 
                    "designations": ["Junior Engineer", "Gram Sevak", "Water Inspector", "Sanitary Inspector"], 
                    "count_per_dist": 10,
                    "loc_type": "taluka" # We'll assign to taluka as "field" location if village not explicitly created
                },
            ]

            total_officers_created = 0

            for dist_name, data in loc_map.items():
                dist_obj = data["dist"]
                talukas = data["talukas"]

                for config in hierarchy_config:
                    for _ in range(config["count_per_dist"]):
                        # Pick random name
                        is_male = random.random() > 0.3
                        fname = random.choice(first_names_male if is_male else first_names_female)
                        lname = random.choice(last_names)
                        full_name = f"{fname} {lname}"
                        
                        # Generate unique username and email
                        random_suffix = random.randint(100, 999)
                        username = f"{fname.lower()}.{lname.lower()}.{random_suffix}"
                        email = f"{fname.lower()}.{lname.lower()}.{random_suffix}@mahagov.in"
                        
                        # Pick department
                        dept = random.choice(list(depts.values()))
                        
                        # Pick location based on level
                        if config["loc_type"] == "dist":
                            loc = dist_obj
                        else:
                            loc = random.choice(talukas)

                        designation = random.choice(config["designations"])
                        emp_id = f"MAHA-{random.randint(100000, 999999)}"

                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password,
                            role=User.Role.OFFICER,
                            full_name=full_name,
                            is_approved=True
                        )

                        # Create the OfficerProfile profile
                        OfficerProfile.objects.create(
                            user=user,
                            department=dept,
                            location=loc,
                            full_name=full_name,
                            employee_id=emp_id,
                            designation=designation,
                            level=config["level"],
                            district=dist_name,
                            taluka=loc.name if loc.type == Location.Type.TALUKA else "",
                            phone=f"+91{random.randint(7000000000, 9999999999)}",
                            is_active=True
                        )
                        
                        officer_logins.append({
                            "Name": full_name,
                            "Username": username,
                            "Email": email,
                            "Password": password,
                            "Designation": designation,
                            "Department": dept.name,
                            "District": dist_name,
                            "Location": loc.name
                        })
                        total_officers_created += 1

            # 5. OUTPUT SUMMARY
            self.stdout.write(self.style.SUCCESS(f"\nSuccessfully created {total_officers_created} realistic officers."))

            # Write to CSV
            with open('officer_logins.csv', 'w', newline='') as csvfile:
                fieldnames = ["Name", "Username", "Email", "Password", "Designation", "Department", "District", "Location"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for login in officer_logins:
                    writer.writerow(login)

            self.stdout.write(self.style.SUCCESS("OfficerProfile directory saved to 'officer_logins.csv'."))

            # Print the directory in the requested format
            self.stdout.write("\n" + "="*50)
            self.stdout.write("REALISTIC OFFICER DIRECTORY")
            self.stdout.write("="*50)
            for login in officer_logins:
                self.stdout.write(f"\nName: {login['Name']}")
                self.stdout.write(f"Email: {login['Email']}")
                self.stdout.write(f"Password: {login['Password']}")
                self.stdout.write(f"Designation: {login['Designation']}")
                self.stdout.write(f"District: {login['District']}")
            self.stdout.write("\n" + "="*50)
