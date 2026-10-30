from django.core.exceptions import ValidationError

from catalog.codes import is_valid_code, is_valid_verses


def validate_code(value: str) -> None:
    if not is_valid_code(value):
        raise ValidationError('Kód písně ve tvaru 523, 101A nebo Z781.')


def validate_verses(value: str | None) -> None:
    if not is_valid_verses(value):
        raise ValidationError('Zadejte „-“ (nemá), „*“ (podle Kancionálu) nebo čísla slok, např. „4“ nebo „4,5“.')
