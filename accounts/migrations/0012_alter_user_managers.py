import accounts.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_alter_user_role"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", accounts.models.UserManager()),
            ],
        ),
    ]
