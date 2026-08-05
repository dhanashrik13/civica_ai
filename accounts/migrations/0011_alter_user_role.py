from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_department_level"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("citizen", "Citizen"),
                    ("officer", "Officer"),
                    ("admin", "Admin"),
                ],
                db_index=True,
                default="citizen",
                max_length=20,
            ),
        ),
    ]
