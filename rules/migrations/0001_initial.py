from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Rule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('celebration', models.CharField(blank=True, max_length=120, verbose_name='slavení')),
                ('category', models.CharField(
                    blank=True,
                    choices=[
                        ('lord', 'Pán Ježíš'),
                        ('virgin_mary', 'Panna Maria'),
                        ('apostle_evangelist', 'apoštolové a evangelisté'),
                        ('martyr', 'mučedníci'),
                        ('pastor', 'duchovní pastýři'),
                        ('doctor', 'učitelé církve'),
                        ('virgin', 'panny'),
                        ('religious', 'řeholníci a řeholnice'),
                        ('saint', 'svatí a světice (obecně)'),
                        ('czech_patron', 'čeští patroni'),
                        ('angel', 'andělé'),
                        ('dedication', 'posvěcení chrámu'),
                        ('dead', 'za zemřelé'),
                    ],
                    max_length=32,
                    verbose_name='kategorie slavení',
                )),
                ('period', models.CharField(blank=True, max_length=48, verbose_name='období')),
                ('season', models.CharField(
                    blank=True,
                    choices=[
                        ('advent', 'doba adventní'),
                        ('christmas', 'doba vánoční'),
                        ('lent', 'doba postní'),
                        ('easter', 'doba velikonoční'),
                        ('ordinary', 'liturgické mezidobí'),
                    ],
                    max_length=16,
                    verbose_name='liturgická doba',
                )),
                ('cycles', models.CharField(blank=True, max_length=3, verbose_name='nedělní cykly')),
                ('day', models.CharField(
                    blank=True,
                    choices=[('', 'kterýkoli den'), ('sunday', 'neděle'), ('weekday', 'všední den')],
                    max_length=8,
                    verbose_name='den',
                )),
                ('min_rank', models.CharField(
                    blank=True,
                    choices=[
                        ('solemnity', 'slavnost a vyšší'),
                        ('feast', 'svátek, neděle a vyšší'),
                        ('memorial', 'památka a vyšší'),
                        ('optional_memorial', 'nezávazná památka a vyšší'),
                    ],
                    max_length=24,
                    verbose_name='nejnižší stupeň',
                )),
                ('dioceses', models.CharField(blank=True, max_length=100, verbose_name='diecéze')),
                ('parts', models.CharField(blank=True, max_length=300, verbose_name='části mše')),
                ('kind', models.CharField(
                    choices=[
                        ('songs', 'písně'),
                        ('neighbours', 'písně ze svátků okolních dnů'),
                        ('note', 'poznámka'),
                        ('silence', 'nic se nezpívá'),
                    ],
                    default='songs',
                    max_length=12,
                    verbose_name='druh',
                )),
                ('strength', models.CharField(
                    choices=[
                        ('prescribed', 'předepsáno'),
                        ('recommended', 'doporučeno'),
                        ('alternative', 'možno též'),
                        ('avoid', 'nevhodné'),
                    ],
                    default='recommended',
                    max_length=12,
                    verbose_name='síla',
                )),
                ('songs', models.CharField(
                    blank=True,
                    help_text=(
                        'Čárkou oddělené: 523 · 813B · Z781 · 838/5 (sloka) · 838/1+3 · 691-695 (rozsah) · '
                        '@mesni_obecne (skupina) · #advent (oddíl Kancionálu)'
                    ),
                    max_length=500,
                    verbose_name='písně',
                )),
                ('window_days', models.PositiveSmallIntegerField(default=7, verbose_name='okno (dny)')),
                ('note', models.TextField(blank=True, verbose_name='poznámka pro uživatele')),
                ('internal', models.TextField(blank=True, verbose_name='interní poznámka')),
                ('page', models.PositiveSmallIntegerField(
                    blank=True,
                    help_text='prázdné = doporučení autora',
                    null=True,
                    verbose_name='strana Direktáře',
                )),
                ('position', models.PositiveIntegerField(default=0, verbose_name='pořadí')),
                ('active', models.BooleanField(default=True, verbose_name='aktivní')),
            ],
            options={
                'verbose_name': 'pravidlo',
                'verbose_name_plural': 'pravidla',
                'ordering': ('position', 'id'),
            },
        ),
    ]
