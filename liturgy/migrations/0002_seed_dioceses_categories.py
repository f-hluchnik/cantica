"""Seed dioceses and celebration categories.

Values are copied here on purpose (migrations must not depend on code that may change later).
Keep in sync with liturgy/constants.py; tests/integration/test_build_and_views.py checks that they match.
"""
from django.db import migrations

DIOCESES = (
    ('czech', 'Česká republika (obecný kalendář)', 'czech'),
    ('cechy', 'Čechy (obecně)', 'czech-cechy'),
    ('morava', 'Morava (obecně)', 'czech-morava'),
    ('pha', 'Arcidiecéze pražská', 'czech-pha'),
    ('ltm', 'Diecéze litoměřická', 'czech-ltm'),
    ('hk', 'Diecéze královéhradecká', 'czech-hk'),
    ('cb', 'Diecéze českobudějovická', 'czech-cb'),
    ('plz', 'Diecéze plzeňská', 'czech-plz'),
    ('olm', 'Arcidiecéze olomoucká', 'czech-olm'),
    ('brn', 'Diecéze brněnská', 'czech-brn'),
    ('oo', 'Diecéze ostravsko-opavská', 'czech-oo'),
)

CATEGORIES = (
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
)


def seed(apps, schema_editor):  # noqa: ANN001, ANN201
    Diocese = apps.get_model('liturgy', 'Diocese')  # noqa: N806
    Category = apps.get_model('liturgy', 'Category')  # noqa: N806
    for position, (code, name, calendar) in enumerate(DIOCESES):
        Diocese.objects.update_or_create(
            code=code,
            defaults={'name': name, 'calapi_calendar': calendar, 'position': position},
        )
    for position, (key, name) in enumerate(CATEGORIES):
        Category.objects.update_or_create(key=key, defaults={'name': name, 'position': position})


class Migration(migrations.Migration):

    dependencies = [
        ('liturgy', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
