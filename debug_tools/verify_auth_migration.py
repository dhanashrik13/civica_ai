import os
import django
import sys
from django.db import connection

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "final_proj.settings")
django.setup()

from accounts.models import CitizenProfile, OfficerProfile, AdminProfile

def verify():
    print("--- SCHEMA VERIFICATION ---")
    
    models = {
        'CitizenProfile': CitizenProfile,
        'OfficerProfile': OfficerProfile,
        'AdminProfile': AdminProfile
    }
    
    results = {}
    
    for name, model in models.items():
        table_name = model._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required_fields = ['username', 'email', 'password_hash', 'is_active', 'last_login', 'created_at', 'updated_at']
        missing = [f for f in required_fields if f not in columns]
        
        count = model.objects.count()
        populated = model.objects.exclude(username=None).exclude(email=None).count()
        
        results[name] = {
            'table': table_name,
            'columns': columns,
            'missing': missing,
            'total_rows': count,
            'populated_rows': populated
        }
        
        print(f"Model: {name}")
        print(f"  Table: {table_name}")
        print(f"  Total Rows: {count}")
        print(f"  Populated Rows (Auth): {populated}")
        if missing:
            print(f"  MISSING FIELDS: {missing}")
        else:
            print(f"  All required fields present and verified in DB.")
        print("-" * 20)
    
    return results

if __name__ == "__main__":
    verify()
