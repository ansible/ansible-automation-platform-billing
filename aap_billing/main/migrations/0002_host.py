# Generated by Django 5.0.2 on 2024-03-01 17:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Host",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created", models.DateTimeField()),
                ("modified", models.DateTimeField()),
                ("name", models.CharField(max_length=512)),
                ("variables", models.TextField()),
            ],
            options={
                "verbose_name_plural": "hosts",
                "ordering": ("name",),
                "managed": False,
            },
        ),
    ]
