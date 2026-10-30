import django.db.models.deletion
from django.db import migrations, models

import catalog.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Song',
            fields=[
                ('code', models.CharField(
                    max_length=8,
                    primary_key=True,
                    serialize=False,
                    validators=[catalog.validators.validate_code],
                    verbose_name='kód',
                )),
                ('number', models.CharField(db_index=True, editable=False, max_length=8, verbose_name='číslo')),
                ('position', models.PositiveIntegerField(default=0, editable=False)),
                ('title', models.CharField(max_length=200, verbose_name='název')),
                ('section', models.CharField(
                    choices=[
                        ('prayers', 'Hlavní společné modlitby'),
                        ('personal_prayer', 'Osobní modlitba'),
                        ('devotions', 'K pobožnostem'),
                        ('hours', 'Denní modlitba církve'),
                        ('advent', 'Adventní písně'),
                        ('christmas', 'Vánoční písně'),
                        ('lent', 'Postní písně'),
                        ('easter', 'Velikonoční písně'),
                        ('ordinaries', 'Zpěvy ke mši a ordinária'),
                        ('mass_general', 'Obecné mešní písně'),
                        ('psalm_responses', 'Odpovědi k žalmům'),
                        ('jesus', 'Písně k Pánu Ježíši'),
                        ('mary_saints', 'Písně o Panně Marii, andělech a svatých'),
                        ('occasional', 'Písně příležitostné'),
                    ],
                    max_length=32,
                    verbose_name='oddíl',
                )),
                ('mass_song', models.BooleanField(blank=True, null=True, verbose_name='mešní píseň')),
                ('communion_verses', models.CharField(
                    blank=True,
                    help_text='prázdné = neověřeno, „-“ = nemá, „*“ = podle Kancionálu, „4,5“ = tyto sloky',
                    max_length=32,
                    null=True,
                    validators=[catalog.validators.validate_verses],
                    verbose_name='k přijímání',
                )),
                ('recessional_verses', models.CharField(
                    blank=True,
                    help_text='prázdné = neověřeno, „-“ = nemá, „*“ = podle Kancionálu, „4,5“ = tyto sloky',
                    max_length=32,
                    null=True,
                    validators=[catalog.validators.validate_verses],
                    verbose_name='na závěr',
                )),
                ('verse_count', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='počet slok')),
                ('reviewed', models.BooleanField(default=False, verbose_name='zkontrolováno')),
                ('note', models.TextField(blank=True, verbose_name='poznámka')),
            ],
            options={
                'verbose_name': 'píseň',
                'verbose_name_plural': 'písně',
                'ordering': ('position',),
            },
        ),
        migrations.CreateModel(
            name='SongGroup',
            fields=[
                ('key', models.CharField(max_length=48, primary_key=True, serialize=False, verbose_name='klíč')),
                ('name', models.CharField(max_length=200, verbose_name='název')),
                ('description', models.TextField(blank=True, verbose_name='popis')),
                ('source_page', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='strana Direktáře')),
            ],
            options={
                'verbose_name': 'skupina písní',
                'verbose_name_plural': 'skupiny písní',
                'ordering': ('key',),
            },
        ),
        migrations.CreateModel(
            name='SongGroupMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memberships',
                    to='catalog.songgroup',
                    verbose_name='skupina',
                )),
                ('song', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='group_memberships',
                    to='catalog.song',
                    verbose_name='píseň',
                )),
            ],
            options={
                'verbose_name': 'píseň ve skupině',
                'verbose_name_plural': 'písně ve skupině',
                'ordering': ('group', 'position', 'id'),
                'constraints': [
                    models.UniqueConstraint(fields=('group', 'song'), name='unique_song_in_group'),
                ],
            },
        ),
        migrations.AddField(
            model_name='songgroup',
            name='songs',
            field=models.ManyToManyField(
                related_name='groups',
                through='catalog.SongGroupMember',
                to='catalog.song',
                verbose_name='písně',
            ),
        ),
        migrations.CreateModel(
            name='CurationState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=0)),
                ('exported_version', models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'stav kurátorských dat',
                'verbose_name_plural': 'stav kurátorských dat',
            },
        ),
    ]
