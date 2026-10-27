from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0002_host"),
    ]

    operations = [
        migrations.AddField(
            model_name="host",
            name="inventory_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
