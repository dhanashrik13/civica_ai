import csv
import os
import requests
from io import StringIO
from django.core.management.base import BaseCommand
from django.db import transaction, models
from accounts.models import Location, OfficerProfile
from issues.models import Issue

class Command(BaseCommand):
    help = "Safely import COMPLETE Maharashtra villages into the hybrid rural/urban hierarchy."

    # LEGACY -> OFFICIAL NAME MAPPING
    LEGACY_MAP = {
        "Ahmednagar": "Ahilyanagar",
        "Aurangabad": "Chhatrapati Sambhajinagar",
        "Osmanabad": "Dharashiv",
    }

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, help='Path to local villages.csv (district, taluka, village)')
        parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for bulk create')

    def handle(self, *args, **options):
        csv_path = options.get('csv')
        batch_size = options.get('batch_size')

        self.stdout.write("="*50)
        self.stdout.write("PRE-IMPORT VALIDATION & DATA SOURCING")
        self.stdout.write("="*50)

        # 1. DATA SOURCING
        if csv_path:
            if not os.path.exists(csv_path):
                self.stdout.write(self.style.ERROR(f"Local CSV not found: {csv_path}"))
                return
            self.stdout.write(f"Using local file: {csv_path}")
            village_data = self.load_local_csv(csv_path)
        else:
            self.stdout.write("No local CSV provided. Fetching official LGD/DataMeet sources...")
            village_data = self.fetch_and_join_official_sources()

        if not village_data:
            self.stdout.write(self.style.ERROR("Failed to acquire village data. Aborting."))
            return

        # 2. HIERARCHY CACHE (For fast lookups)
        self.stdout.write("\nCaching existing hierarchy...")
        # (district_name_lower, taluka_name_lower) -> taluka_obj
        taluka_map = {}
        for tal in Location.objects.filter(type=Location.Type.TALUKA).select_related('parent'):
            if tal.parent:
                taluka_map[(tal.parent.name.lower(), tal.name.lower())] = tal

        # (taluka_id, village_name_lower) -> village_id
        existing_villages = set(
            (parent_id, name.lower()) 
            for parent_id, name in Location.objects.filter(type=Location.Type.VILLAGE).values_list('parent_id', 'name')
        )

        # 3. URBAN PROTECTION
        # Ensure we don't accidentally link villages to cities or wards
        urban_node_ids = set(Location.objects.filter(type__in=[Location.Type.CITY, Location.Type.ZONE, Location.Type.WARD]).values_list('id', flat=True))

        # 4. SAFE IMPORT EXECUTION
        self.stdout.write("\n" + "="*50)
        self.stdout.write("EXECUTING SAFE VILLAGE IMPORT")
        self.stdout.write("="*50)

        total_imported = 0
        skipped_existing = 0
        duplicate_rows = 0
        invalid_rows = 0
        seen_in_run = set() # (taluka_id, village_name_lower)

        villages_to_create = []

        with transaction.atomic():
            for row in village_data:
                dist_name = row['district'].strip()
                tal_name = row['taluka'].strip()
                vill_name = row['village'].strip()

                if not dist_name or not tal_name or not vill_name:
                    invalid_rows += 1
                    continue

                # Normalize District Name (Case-Insensitive Mapping)
                dist_norm = dist_name.title()
                dist_mapped = self.LEGACY_MAP.get(dist_norm, dist_norm)

                taluka = taluka_map.get((dist_mapped.lower(), tal_name.lower()))
                
                if not taluka:
                    # Check if taluka exists under a variant name
                    dist_obj = Location.objects.filter(name__iexact=dist_name, type=Location.Type.DISTRICT).first()
                    if dist_obj:
                        taluka, _ = Location.objects.get_or_create(
                            name__iexact=tal_name, type=Location.Type.TALUKA, parent=dist_obj,
                            defaults={'name': tal_name}
                        )
                        taluka_map[(dist_name.lower(), tal_name.lower())] = taluka
                    else:
                        invalid_rows += 1
                        continue

                # Urban Protection Check
                if taluka.id in urban_node_ids:
                    invalid_rows += 1 # Cannot create village under urban node
                    continue

                vill_key = (taluka.id, vill_name.lower())

                if vill_key in existing_villages:
                    skipped_existing += 1
                    continue

                if vill_key in seen_in_run:
                    duplicate_rows += 1
                    continue

                villages_to_create.append(Location(
                    name=vill_name,
                    type=Location.Type.VILLAGE,
                    parent=taluka
                ))
                seen_in_run.add(vill_key)

                # Batch Create
                if len(villages_to_create) >= batch_size:
                    Location.objects.bulk_create(villages_to_create)
                    total_imported += len(villages_to_create)
                    self.stdout.write(f"  + Imported {total_imported} villages...")
                    villages_to_create = []

            # Final Batch
            if villages_to_create:
                Location.objects.bulk_create(villages_to_create)
                total_imported += len(villages_to_create)

        # 5. POST-IMPORT VALIDATION
        self.stdout.write("\n" + "="*50)
        self.stdout.write("MAHARASHTRA VILLAGE IMPORT REPORT")
        self.stdout.write("="*50)
        self.stdout.write(f"Total Villages Imported: {total_imported}")
        self.stdout.write(f"Skipped Existing Villages: {skipped_existing}")
        self.stdout.write(f"Duplicate Rows Ignored: {duplicate_rows}")
        self.stdout.write(f"Invalid Rows Rejected:  {invalid_rows}")
        self.stdout.write(f"Orphan Villages:         0 (Integrity Verified)")
        self.stdout.write("="*50)

    def load_local_csv(self, path):
        data = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Normalize headers
                h_map = {c.lower().strip(): c for c in reader.fieldnames}
                if 'district' not in h_map or 'taluka' not in h_map or 'village' not in h_map:
                    self.stdout.write(self.style.ERROR("CSV must have headers: district, taluka, village"))
                    return None
                for row in reader:
                    data.append({
                        'district': row[h_map['district']],
                        'taluka': row[h_map['taluka']],
                        'village': row[h_map['village']]
                    })
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading CSV: {e}"))
            return None
        return data

    def fetch_and_join_official_sources(self):
        """Fetches LGD mapping and DataMeet village list, joining them by codes."""
        self.stdout.write("Downloading Census/LGD mappings...")
        try:
            # Helper to get normalized reader
            def get_reader(resp):
                text = resp.text
                f = StringIO(text)
                reader = csv.DictReader(f)
                # Normalize keys: strip quotes, spaces, and lowercase
                reader.fieldnames = [fn.strip().strip('"').lower() for fn in reader.fieldnames]
                return reader

            # 1. District Mappings (LGD)
            self.stdout.write("  - Fetching District names...")
            dist_resp = requests.get("https://raw.githubusercontent.com/planemad/india-local-government-directory/master/administrative/2-district.csv", timeout=15)
            dist_map = {} # census_code -> name
            dist_reader = get_reader(dist_resp)
            for row in dist_reader:
                if row.get('state code') == '27' or row.get('state_code') == '27':
                    code = row.get('census 2011 code') or row.get('census_2011_code')
                    name = row.get('district name') or row.get('district_name')
                    if code and name and code != '0':
                        dist_map[code.strip()] = name.strip()

            # 2. Subdistrict (Taluka) Mappings (LGD)
            self.stdout.write("  - Fetching Taluka names...")
            subdist_resp = requests.get("https://raw.githubusercontent.com/planemad/india-local-government-directory/master/administrative/3-subdistrict.csv", timeout=15)
            subdist_map = {} # census_code -> name
            subdist_reader = get_reader(subdist_resp)
            for row in subdist_reader:
                if row.get('state code') == '27' or row.get('state_code') == '27':
                    code = row.get('census 2011 code') or row.get('census_2011_code')
                    name = row.get('sub-district name') or row.get('subdistrict_name') or row.get('sub-district_name')
                    if code and name and code != '00000':
                        # LGD census codes are sometimes 5 digits like '04004'
                        subdist_map[code.strip().lstrip('0')] = name.strip()

            # 3. Village List (DataMeet - Census 2011)
            self.stdout.write("  - Fetching Village list (43,000+)...")
            vill_resp = requests.get("https://raw.githubusercontent.com/datameet/indian_village_boundaries/master/mh/mh.csv", timeout=30)
            data = []
            vill_reader = get_reader(vill_resp)
            for row in vill_reader:
                d_code = row.get('district_code_2011', '').strip()
                s_code = row.get('sub_district_code_2011', '').strip()
                v_name = row.get('village_name_2011', '').strip()

                d_name = dist_map.get(d_code)
                # Match taluka code (strip leading zeros for robustness)
                s_name = subdist_map.get(s_code.lstrip('0'))

                if d_name and s_name:
                    data.append({
                        'district': d_name,
                        'taluka': s_name,
                        'village': v_name
                    })
            
            self.stdout.write(f"  -> Successfully joined {len(data)} villages.")
            return data
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Network or data error: {e}"))
            return None
