# Generated by Django 5.1.3 on 2024-11-23 10:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('songs', '0002_song_feast'),
    ]

    operations = [
        migrations.AddField(
            model_name='song',
            name='liturgical_season',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
