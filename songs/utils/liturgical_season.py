from enum import Enum
from typing import Optional


class LiturgicalSeasonEnum(Enum):
    ADVENT = 'advent'
    CHRISTMAS = 'christmas'
    LENT = 'lent'
    EASTER = 'easter'
    ORDINARY = 'ordinary'
    JESUS_CHRIST = 'jesus christ'
    VIRGIN_MARY = 'virgin mary'
    SAINTS = 'saints'
    OCCASIONAL = 'occasional'

    @classmethod
    def from_string(cls, value: Optional[str]) -> Optional['LiturgicalSeasonEnum']:
        """
        Get the LiturgicalSeason instance corresponding to the given string value.
        Returns None if the value does not match any enum member.
        """
        try:
            return cls(value)
        except ValueError:
            return None
