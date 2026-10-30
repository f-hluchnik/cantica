import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Diocese',
            fields=[
                ('code', models.CharField(max_length=16, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('calapi_calendar', models.CharField(max_length=32, unique=True)),
                ('position', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'diecéze',
                'verbose_name_plural': 'diecéze',
                'ordering': ('position',),
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('key', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('position', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'kategorie slavení',
                'verbose_name_plural': 'kategorie slavení',
                'ordering': ('position',),
            },
        ),
        migrations.CreateModel(
            name='Celebration',
            fields=[
                ('key', models.CharField(max_length=120, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=250)),
                ('categories_reviewed', models.BooleanField(default=False)),
                ('categories', models.ManyToManyField(blank=True, related_name='celebrations', to='liturgy.category')),
            ],
            options={
                'verbose_name': 'slavení',
                'verbose_name_plural': 'slavení',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='CelebrationAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=250)),
                ('celebration', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='aliases',
                    to='liturgy.celebration',
                )),
            ],
            options={
                'verbose_name': 'jiný název',
                'verbose_name_plural': 'jiné názvy',
                'ordering': ('title',),
            },
        ),
        migrations.CreateModel(
            name='CalendarDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('season', models.CharField(
                    choices=[
                        ('advent', 'doba adventní'),
                        ('christmas', 'doba vánoční'),
                        ('lent', 'doba postní'),
                        ('easter', 'doba velikonoční'),
                        ('ordinary', 'liturgické mezidobí'),
                    ],
                    max_length=16,
                )),
                ('season_week', models.PositiveSmallIntegerField()),
                ('sunday_cycle', models.CharField(max_length=1)),
                ('ferial_cycle', models.PositiveSmallIntegerField()),
                ('diocese', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='days',
                    to='liturgy.diocese',
                )),
            ],
            options={
                'verbose_name': 'den',
                'verbose_name_plural': 'dny',
                'ordering': ('date',),
                'constraints': [
                    models.UniqueConstraint(fields=('diocese', 'date'), name='unique_day_per_diocese'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Occurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField()),
                ('title', models.CharField(max_length=250)),
                ('rank_label', models.CharField(max_length=40)),
                ('rank_num', models.DecimalField(decimal_places=2, max_digits=4)),
                ('colour', models.CharField(max_length=16)),
                ('celebration', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='occurrences',
                    to='liturgy.celebration',
                )),
                ('day', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='occurrences',
                    to='liturgy.calendarday',
                )),
            ],
            options={
                'verbose_name': 'slavení v kalendáři',
                'verbose_name_plural': 'slavení v kalendáři',
                'ordering': ('day', 'position'),
                'constraints': [
                    models.UniqueConstraint(fields=('day', 'position'), name='unique_occurrence_position'),
                ],
            },
        ),
        migrations.CreateModel(
            name='CalendarBuild',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('built_at', models.DateTimeField(auto_now_add=True)),
                ('source_digest', models.CharField(max_length=64)),
                ('first_date', models.DateField()),
                ('last_date', models.DateField()),
                ('days', models.PositiveIntegerField()),
            ],
            options={
                'verbose_name': 'sestavení kalendáře',
                'verbose_name_plural': 'sestavení kalendáře',
                'ordering': ('-built_at',),
            },
        ),
    ]
