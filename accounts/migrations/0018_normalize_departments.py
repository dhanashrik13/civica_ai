from django.db import migrations

def run_normalization(apps, schema_editor):
    from accounts.services import normalize_departments
    import sys
    
    # We use sys.stdout as a proxy for the stdout object expected by the service
    normalize_departments(stdout=sys.stdout)

def reverse_normalization(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0017_officer_city_officer_ward_alter_department_level_and_more'),
        ('issues', '0027_alter_issue_city_alter_issue_district_and_more'),
    ]

    operations = [
        migrations.RunPython(run_normalization, reverse_normalization),
    ]
