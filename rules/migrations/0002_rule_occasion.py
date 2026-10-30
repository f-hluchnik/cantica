from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rules', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='occasion',
            field=models.CharField(
                blank=True,
                choices=[
                    ('krest', 'Křest'),
                    ('birmovani', 'Biřmování'),
                    ('pomazani', 'Pomazání nemocných'),
                    ('svatba', 'Svatba'),
                    ('pohreb', 'Pohřeb'),
                    ('bohosluzba_slova', 'Bohoslužba slova'),
                ],
                help_text='pravidlo pro příležitost (křest, pohřeb, …) se nikdy neuplatní na kalendářní den',
                max_length=24,
                verbose_name='příležitost',
            ),
        ),
    ]
