# Generated manually for IngestedJob + MatchResult models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestedJob",
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
                ("source_job_id", models.CharField(max_length=255, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("company", models.CharField(blank=True, max_length=255, null=True)),
                ("location", models.CharField(blank=True, max_length=255, null=True)),
                ("remote", models.BooleanField(default=False)),
                ("salary_min", models.IntegerField(blank=True, null=True)),
                ("salary_max", models.IntegerField(blank=True, null=True)),
                ("salary_currency", models.CharField(default="USD", max_length=10)),
                ("required_skills", models.JSONField(default=list)),
                ("preferred_skills", models.JSONField(default=list)),
                ("years_experience", models.IntegerField(blank=True, null=True)),
                (
                    "employment_type",
                    models.CharField(blank=True, max_length=50, null=True),
                ),
                ("description", models.TextField(blank=True, null=True)),
                ("source", models.CharField(max_length=50)),
                ("raw_payload", models.JSONField(default=dict)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="MatchResult",
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
                ("user_id", models.IntegerField()),
                ("user_name", models.CharField(max_length=255)),
                ("user_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("match_score", models.FloatField()),
                ("skills", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, max_length=255, null=True)),
                ("years_of_experience", models.IntegerField(blank=True, null=True)),
                ("experience_level", models.CharField(blank=True, max_length=50, null=True)),
                ("salary_range", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ingested_job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matches",
                        to="api.ingestedjob",
                    ),
                ),
            ],
            options={
                "ordering": ["-match_score"],
            },
        ),
    ]
