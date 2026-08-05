from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Location, OfficerProfile

class Command(BaseCommand):
    help = "Setup realistic Urban Municipal Hierarchy (PMC/PCMC) and migrate urban officers."

    def handle(self, *args, **options):
        # 1. IDENTIFY PARENT DISTRICT
        pune_dist = Location.objects.filter(name="Pune", type=Location.Type.DISTRICT).first()
        if not pune_dist:
            self.stdout.write(self.style.ERROR("Pune District not found. Please seed districts first."))
            return

        urban_data = {
            "Pune Municipal Corporation (PMC)": {
                "Zone 1": ["Kothrud", "Bavdhan", "Warje"],
                "Zone 2": ["Shivajinagar", "Baner", "Aundh"],
                "Zone 3": ["Viman Nagar", "Wadgaon Sheri", "Yerawada"],
            },
            "Pimpri-Chinchwad Municipal Corporation (PCMC)": {
                "Zone A": ["Pimpri", "Chinchwad", "Bhosari"],
                "Zone B": ["Nigdi", "Akurdi", "Sangvi"],
            }
        }

        all_wards = []

        with transaction.atomic():
            self.stdout.write("Creating Urban Hierarchy...")
            for city_name, zones in urban_data.items():
                city, created = Location.objects.get_or_create(
                    name=city_name,
                    type=Location.Type.CITY,
                    parent=pune_dist
                )
                if created:
                    self.stdout.write(f"  + Created City: {city_name}")

                for zone_name, wards in zones.items():
                    zone, created = Location.objects.get_or_create(
                        name=zone_name,
                        type=Location.Type.ZONE,
                        parent=city
                    )
                    if created:
                        self.stdout.write(f"    + Created Zone: {zone_name}")

                    for ward_name in wards:
                        ward, created = Location.objects.get_or_create(
                            name=ward_name,
                            type=Location.Type.WARD,
                            parent=zone
                        )
                        if created:
                            self.stdout.write(f"      + Created Ward: {ward_name}")
                        all_wards.append(ward)

            # 2. MIGRATE OFFICERS FROM PUNE CITY TALUKA
            self.stdout.write("\nMigrating Officers from 'Pune City' taluka...")
            pune_city_taluka = Location.objects.filter(name="Pune City", type=Location.Type.TALUKA).first()
            
            if pune_city_taluka:
                urban_officers = OfficerProfile.objects.filter(location=pune_city_taluka)
                count = urban_officers.count()
                
                if count > 0:
                    for i, officer in enumerate(urban_officers):
                        # Round-robin assignment to wards
                        assigned_ward = all_wards[i % len(all_wards)]
                        
                        officer.location = assigned_ward
                        officer.level = OfficerProfile.Level.WARD
                        
                        # Populate denormalized fields
                        # Trace up: Ward -> Zone -> City -> District
                        officer.ward = assigned_ward.name
                        officer.zone = assigned_ward.parent.name
                        officer.city = assigned_ward.parent.parent.name
                        officer.district = assigned_ward.parent.parent.parent.name
                        officer.taluka = "" # Clear taluka as it's now urban
                        officer.village = ""
                        
                        officer.save()
                        self.stdout.write(f"  -> Migrated {officer.user.username} to {assigned_ward.name} Ward ({officer.city})")
                    
                    self.stdout.write(self.style.SUCCESS(f"Successfully migrated {count} officers to urban hierarchy."))
                else:
                    self.stdout.write("No officers found in 'Pune City' taluka.")
            else:
                self.stdout.write("Pune City taluka not found, skipping officer migration.")

        self.stdout.write(self.style.SUCCESS("\nUrban Municipal Hierarchy Setup Complete."))
