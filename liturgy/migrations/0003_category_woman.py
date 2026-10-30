"""Add the category "světice" (women saints: 845, Direktář p. 9) and renumber the positions.

Values are copied here on purpose (migrations must not depend on code that may change later).
tests/integration/test_build_and_views.py checks that the DB matches liturgy/constants.py.
"""
from django.db import migrations

CATEGORIES = (
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
)


def seed(apps, schema_editor):  # noqa: ANN001, ANN201
    Category = apps.get_model('liturgy', 'Category')  # noqa: N806
    for position, (key, name) in enumerate(CATEGORIES):
        Category.objects.update_or_create(key=key, defaults={'name': name, 'position': position})


class Migration(migrations.Migration):

    dependencies = [
        ('liturgy', '0002_seed_dioceses_categories'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
