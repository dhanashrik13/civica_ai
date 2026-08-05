from django.db import migrations, models


def normalize_issue_statuses(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")

    Issue.objects.filter(status="in_progress").update(status="assigned")
    Issue.objects.filter(status="rejected").update(status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0010_alter_issue_assigned_to_alter_issue_department"),
    ]

    operations = [
        migrations.RunPython(normalize_issue_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="issue",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("assigned", "Assigned"),
                    ("resolved", "Resolved"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
