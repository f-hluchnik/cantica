# Generated by Django 5.1.3 on 2024-11-24 21:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feasts', '0003_alter_feast_slug'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='feast',
            name='date',
        ),
        migrations.RemoveField(
            model_name='feast',
            name='degree',
        ),
        migrations.CreateModel(
            name='LiturgicalCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('season', models.CharField(max_length=50)),
                ('celebrations', models.ManyToManyField(related_name='calendar_dates', to='feasts.feast')),
            ],
        ),
    ]
