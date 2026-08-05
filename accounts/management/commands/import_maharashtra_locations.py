import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Location

class Command(BaseCommand):
    help = "Import the complete Maharashtra administrative hierarchy (Districts, Talukas, and optionally Villages)."

    # Complete Maharashtra District -> Talukas Mapping (Real Data)
    MAHARASHTRA_HIERARCHY = {
        "Ahilyanagar": ["Nagar", "Shevgaon", "Pathardi", "Parner", "Sangamner", "Kopargaon", "Akole", "Shrirampur", "Nevasa", "Rahata", "Rahuri", "Shrigonda", "Karjat", "Jamkhed"],
        "Akola": ["Akola", "Akot", "Telhara", "Balapur", "Patur", "Murtajapur", "Barshitakli"],
        "Amravati": ["Amravati", "Bhatkuli", "Nandgaon Khandeshwar", "Dharni", "Chikhaldara", "Achalpur", "Chandurbazar", "Morshi", "Warud", "Daryapur", "Anjangaon-Surji", "Chandur", "Dhamangaon", "Tiosa"],
        "Beed": ["Beed", "Georai", "Patoda", "Shirur-Kasar", "Ashti", "Majalgaon", "Wadwani", "Kaij", "Dharur", "Parli", "Ambajogai"],
        "Bhandara": ["Bhandara", "Tumsar", "Pauni", "Mohadi", "Sakoli", "Lakhani", "Lakhandur"],
        "Buldhana": ["Buldhana", "Chikhli", "Deulgaon Raja", "Jalgaon Jamod", "Sangrampur", "Malkapur", "Motala", "Nandura", "Khamgaon", "Shegaon", "Mehkar", "Sindkhed Raja", "Lonar"],
        "Chandrapur": ["Chandrapur", "Saoli", "Mul", "Ballarpur", "Pombhurna", "Gondpimpri", "Warora", "Chimur", "Bhadravati", "Bramhapuri", "Nagbhid", "Sindewahi", "Rajura", "Korpana", "Jiwati"],
        "Chhatrapati Sambhajinagar": ["Aurangabad", "Kannad", "Soegaon", "Sillod", "Phulambri", "Khuldabad", "Vaijapur", "Gangapur", "Paithan"],
        "Dharashiv": ["Osmanabad", "Tuljapur", "Bhum", "Paranda", "Washi", "Kalamb", "Lohara", "Umarga"],
        "Dhule": ["Dhule", "Sakri", "Sindkheda", "Shirpur"],
        "Gadchiroli": ["Gadchiroli", "Dhanora", "Chamorshi", "Mulchera", "Desaiganj", "Armori", "Kurkheda", "Korchi", "Aheri", "Etapalli", "Bhamragad", "Sironcha"],
        "Gondia": ["Gondia", "Goregaon", "Salekasa", "Tiroda", "Deori", "Amgaon", "Arjuni Morgaon", "Sadak-Arjuni"],
        "Hingoli": ["Hingoli", "Sengaon", "Kalamnuri", "Basmath", "Aundha Nagnath"],
        "Jalgaon": ["Jalgaon", "Jamner", "Erandol", "Dharangaon", "Bhusawal", "Raver", "Muktainagar", "Bodwad", "Yawal", "Amalner", "Parola", "Chopda", "Pachora", "Bhadgaon", "Chalisgaon"],
        "Jalna": ["Jalna", "Bhokardan", "Jafrabad", "Badnapur", "Ambad", "Ghansawangi", "Partur", "Mantha"],
        "Kolhapur": ["Karvir", "Panhala", "Shahuwadi", "Kagal", "Hatkanangale", "Shirol", "Radhanagari", "Gaganbawada", "Bhudargad", "Gadhinglaj", "Chandgad", "Ajra"],
        "Latur": ["Latur", "Renapur", "Ausa", "Ahmedpur", "Jalkot", "Chakur", "Shirur Anantpal", "Nilanga", "Deoni", "Udgir"],
        "Mumbai City": [],
        "Mumbai Suburban": ["Kurla", "Andheri", "Borivali"],
        "Nagpur": ["Nagpur Urban", "Nagpur Rural", "Kamptee", "Hingna", "Katol", "Narkhed", "Savner", "Kalameshwar", "Ramtek", "Mouda", "Parseoni", "Umred", "Kuhi", "Bhiwapur"],
        "Nanded": ["Nanded", "Ardhapur", "Mudkhed", "Bhokar", "Umri", "Loha", "Kandhar", "Kinwat", "Himayatnagar", "Hadgaon", "Mahur", "Deglur", "Mukhed", "Dharmabad", "Biloli", "Naigaon"],
        "Nandurbar": ["Nandurbar", "Navapur", "Shahada", "Talode", "Akkalkuwa", "Dhadgaon"],
        "Nashik": ["Nashik", "Igatpuri", "Dindori", "Peth", "Trimbakeshwar", "Kalwan", "Deola", "Surgana", "Baglan", "Malegaon", "Nandgaon", "Chandwad", "Niphad", "Sinnar", "Yeola"],
        "Palghar": ["Palghar", "Vasai", "Dahanu", "Talasari", "Jawhar", "Mokhada", "Vada", "Vikramgad"],
        "Parbhani": ["Parbhani", "Sonpeth", "Gangakhed", "Palam", "Purna", "Sailu", "Jintur", "Manwath", "Pathri"],
        "Pune": ["Pune City", "Haveli", "Khed", "Junnar", "Ambegaon", "Maval", "Mulshi", "Shirur", "Purandhar (Saswad)", "Velhe", "Bhor", "Baramati", "Indapur", "Daund"],
        "Raigad": ["Pen", "Alibag", "Murud", "Panvel", "Uran", "Karjat", "Khalapur", "Mangaon", "Tala", "Roha", "Sudhagad-Pali", "Mahad", "Poladpur", "Shrivardhan", "Mhasala"],
        "Ratnagiri": ["Ratnagiri", "Sangameshwar", "Lanja", "Rajapur", "Chiplun", "Guhagar", "Dapoli", "Mandangad", "Khed"],
        "Sangli": ["Miraj", "Kavathemahankal", "Tasgaon", "Jat", "Walwa", "Shirala", "Khanapur (Vita)", "Atpadi", "Palus", "Kadegaon"],
        "Satara": ["Satara", "Jaoli", "Koregaon", "Wai", "Mahabaleshwar", "Khandala", "Phaltan", "Maan", "Khatav", "Karad", "Patan"],
        "Sindhudurg": ["Kankavli", "Vaibhavwadi", "Devgad", "Malwan", "Sawantwadi", "Kudal", "Vengurla", "Dodamarg"],
        "Solapur": ["North Solapur", "Barshi", "South Solapur", "Akkalkot", "Madha", "Karmala", "Pandharpur", "Mohol", "Malshiras", "Mangalvedhe", "Sangole"],
        "Thane": ["Thane", "Kalyan", "Murbad", "Bhiwandi", "Shahapur", "Ulhasnagar", "Ambarnath"],
        "Wardha": ["Wardha", "Deoli", "Seloo", "Arvi", "Ashti", "Karanja", "Hinganghat", "Samudrapur"],
        "Washim": ["Washim", "Malegaon", "Risod", "Mangrulpir", "Karanja", "Manora"],
        "Yavatmal": ["Yavatmal", "Arni", "Babhulgaon", "Kalamb", "Darwha", "Digras", "Ner", "Pusad", "Umarkhed", "Mahagaon", "Kelapur", "Ralegaon", "Ghatanji", "Wani", "Maregaon", "Zari Jamani"],
    }

    # Handle Legacy/Renamed Districts
    LEGACY_MAP = {
        "Ahmednagar": "Ahilyanagar",
        "Aurangabad": "Chhatrapati Sambhajinagar",
        "Osmanabad": "Dharashiv",
    }

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, help='Path to CSV file with "district, taluka, village" columns')
        parser.add_argument('--clear', action='store_true', help='Clear existing locations before import (CAUTION)')

    def handle(self, *args, **options):
        csv_path = options.get('csv')
        
        if options['clear']:
            self.stdout.write(self.style.WARNING("Clearing all Location records..."))
            Location.objects.all().delete()

        # 1. Audit and Import Districts & Talukas
        self.stdout.write("Seeding Districts and Talukas...")
        
        with transaction.atomic():
            for dist_name, talukas in self.MAHARASHTRA_HIERARCHY.items():
                # Normalize district name
                dist_name = dist_name.strip()
                dist_obj, created = Location.objects.get_or_create(
                    name__iexact=dist_name, 
                    type=Location.Type.DISTRICT,
                    defaults={'name': dist_name}
                )
                if created:
                    self.stdout.write(f"  + District: {dist_name}")
                
                for tal_name in talukas:
                    tal_name = tal_name.strip()
                    tal_obj, created = Location.objects.get_or_create(
                        name__iexact=tal_name,
                        type=Location.Type.TALUKA,
                        parent=dist_obj,
                        defaults={'name': tal_name}
                    )
                    if created:
                        pass # Too many to log individual created talukas

        # 2. Import Villages from CSV if provided
        if csv_path:
            if not os.path.exists(csv_path):
                self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            else:
                self.import_villages(csv_path)

        self.print_summary()

    def import_villages(self, csv_path):
        self.stdout.write(f"Importing villages from {csv_path}...")
        
        # Load all existing Talukas into memory for fast lookup
        taluka_map = {} # (district_name_lower, taluka_name_lower) -> taluka_obj
        for tal in Location.objects.filter(type=Location.Type.TALUKA).select_related('parent'):
            taluka_map[(tal.parent.name.lower(), tal.name.lower())] = tal

        villages_to_create = []
        seen_villages = set() # To prevent duplicates in current run
        
        # Get existing villages to prevent duplicates across runs
        existing_villages = set(Location.objects.filter(type=Location.Type.VILLAGE).values_list('parent_id', 'name__lower'))

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f) # Expects columns: district, taluka, village
            
            # If no headers, try reading as raw list
            if not reader.fieldnames or 'village' not in [c.lower() for c in reader.fieldnames]:
                f.seek(0)
                reader = csv.reader(f)
                headers = [h.lower().strip() for h in next(reader)]
                # Map headers to indices
                try:
                    dist_idx = headers.index('district')
                    tal_idx = headers.index('taluka')
                    vill_idx = headers.index('village')
                except ValueError:
                    self.stdout.write(self.style.ERROR("CSV must have headers: district, taluka, village"))
                    return

                for row in reader:
                    self.process_village_row(row[dist_idx], row[tal_idx], row[vill_idx], 
                                           taluka_map, existing_villages, seen_villages, villages_to_create)
            else:
                # Case-insensitive header matching
                h_map = {c.lower(): c for c in reader.fieldnames}
                for row in reader:
                    self.process_village_row(row[h_map['district']], row[h_map['taluka']], row[h_map['village']], 
                                           taluka_map, existing_villages, seen_villages, villages_to_create)

        if villages_to_create:
            self.stdout.write(f"Bulk creating {len(villages_to_create)} villages...")
            # Batch size for SQLite compatibility and performance
            for i in range(0, len(villages_to_create), 999):
                Location.objects.bulk_create(villages_to_create[i:i+999])
            self.stdout.write(self.style.SUCCESS(f"Successfully imported {len(villages_to_create)} new villages."))
        else:
            self.stdout.write("No new villages to import.")

    def process_village_row(self, dist_name, tal_name, vill_name, taluka_map, existing_villages, seen_villages, villages_to_create):
        dist_name = dist_name.strip()
        tal_name = tal_name.strip()
        vill_name = vill_name.strip()

        # Handle renamed districts
        if dist_name in self.LEGACY_MAP:
            dist_name = self.LEGACY_MAP[dist_name]

        taluka = taluka_map.get((dist_name.lower(), tal_name.lower()))
        if not taluka:
            # Maybe the taluka exists under a slightly different name or we need to create it
            # But according to rules, we maintain correct hierarchy. 
            # We'll skip if taluka is not found to prevent orphans, or create it if district exists.
            dist_obj = Location.objects.filter(name__iexact=dist_name, type=Location.Type.DISTRICT).first()
            if dist_obj:
                taluka, _ = Location.objects.get_or_create(
                    name__iexact=tal_name, type=Location.Type.TALUKA, parent=dist_obj,
                    defaults={'name': tal_name}
                )
                taluka_map[(dist_name.lower(), tal_name.lower())] = taluka
            else:
                return # Skip if district unknown

        vill_key = (taluka.id, vill_name.lower())
        if vill_key not in existing_villages and vill_key not in seen_villages:
            villages_to_create.append(Location(
                name=vill_name,
                type=Location.Type.VILLAGE,
                parent=taluka
            ))
            seen_villages.add(vill_key)

    def print_summary(self):
        dist_count = Location.objects.filter(type=Location.Type.DISTRICT).count()
        tal_count = Location.objects.filter(type=Location.Type.TALUKA).count()
        vill_count = Location.objects.filter(type=Location.Type.VILLAGE).count()

        self.stdout.write("\n" + "="*50)
        self.stdout.write("MAHARASHTRA ADMINISTRATIVE HIERARCHY SUMMARY")
        self.stdout.write("="*50)
        self.stdout.write(f"Districts: {dist_count}")
        self.stdout.write(f"Talukas:   {tal_count}")
        self.stdout.write(f"Villages:  {vill_count}")
        self.stdout.write("="*50)

        # Print top 5 districts by taluka count
        districts = Location.objects.filter(type=Location.Type.DISTRICT).annotate(tal_count=models.Count('children')).order_by('-tal_count')[:5]
        self.stdout.write("\nTop Districts by Taluka Count:")
        for d in districts:
            self.stdout.write(f" - {d.name}: {d.tal_count} talukas")
        
        self.stdout.write("\n" + "="*50)

from django.db import models
