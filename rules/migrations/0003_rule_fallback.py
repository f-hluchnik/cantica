from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rules', '0002_rule_occasion'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='fallback',
            field=models.BooleanField(
                default=False,
                help_text='neuplatní se, má-li den pro tuto část konkrétnější píseň (např. ▲ píseň světce)',
                verbose_name='jen bez vlastní písně',
            ),
        ),
        migrations.AlterField(
            model_name='rule',
            name='category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('lord', 'Pán Ježíš'),
                    ('virgin_mary', 'Panna Maria'),
                    ('apostle_evangelist', 'apoštolové a evangelisté'),
                    ('martyr', 'mučedníci'),
                    ('pastor', 'duchovní pastýři'),
                    ('doctor', 'učitelé církve'),
                    ('virgin', 'panny'),
                    ('woman', 'světice'),
                    ('religious', 'řeholníci a řeholnice'),
                    ('saint', 'svatí a světice (obecně)'),
                    ('czech_patron', 'čeští patroni'),
                    ('angel', 'andělé'),
                    ('dedication', 'posvěcení chrámu'),
                    ('dead', 'za zemřelé'),
                ],
                max_length=32,
                verbose_name='kategorie slavení',
            ),
        ),
    ]
