import requests
from celebrations.models import Celebration, CelebrationType, LiturgicalCalendarEvent
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from django.utils.text import slugify
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiturgyAPIClient:
    """Fetch today's liturgical calendar data and update database."""

    API_URL_DAY = 'http://calapi.inadiutorium.cz/api/v0/cs/calendars/czech/{year}/{month}/{day}'
    API_URL_MONTH = 'http://calapi.inadiutorium.cz/api/v0/cs/calendars/czech/{year}/{month}'

    def fetch_day(self, day: Optional[date], *args, **kwargs) -> None:
        """
        Fetch data for provided day.

        Args:
            day: default value: today's date
        """
        day = day or datetime.now().date()
        logger.info('Fetching data for day {day}'.format(day=date))
        response = requests.get(self.API_URL_DAY.format(year=day.year, month=day.month, day=day.day))
        response.raise_for_status()
        data = response.json()
        self.update_database(data)

    def fetch_month(self, year: int, month: int) -> None:
        """
        Fetch data for provided month and year.

        Args:
            year:
            month:
        """
        logger.info('Fetching data for month {year}-{month}'.format(year=year, month=month))
        response = requests.get(self.API_URL_MONTH.format(year=year, month=month))
        response.raise_for_status()
        data = response.json()
        for day in data:
            self.update_database(day)

    def update_database(self, data: Dict) -> None:
        """
        Update database with provided data.
        The data should have this structure:
        {
            "date": "2025-06-01",
            "season": "easter",
            "season_week": 7,
            "celebrations":[
                {
                    "title": "7th Sunday of Easter",
                    "colour": "white",
                    "rank": "Primary liturgical days",
                    "rank_num":1.2
                }
            ],
            "weekday": "sunday"
        },
        Creates entry for LiturgicalCalendarEvent and adds Celebrations and CelebrationTypes, which are infered from the celebration title.
        """
        date = data.get('date')
        season = data.get('season')

        # Create or update LiturgicalCalendarEvent entry
        liturgical_calendar_event, _ = LiturgicalCalendarEvent.objects.update_or_create(
            date=date,
            defaults={
                'season': season,
            }
        )

        # Process celebrations
        for celebration in data.get('celebrations', []):
            slug = slugify(celebration["title"])

            # Create or update CelebrationType(s)
            types = self.infer_types(celebration["title"])
            celebration_types = []
            for celebration_type_name in types:
                celebration_type, _ = CelebrationType.objects.get_or_create(name=celebration_type_name)
                celebration_types.append(celebration_type)

            # Create or update Celebration
            celebration, _ = Celebration.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': celebration.get('title'),
                }
            )
            celebration.types.set(celebration_types)
            celebration.save()

            # Add celebration to the LiturgicalCalendarEvent entry
            liturgical_calendar_event.celebrations.add(celebration)
        logger.info("Day {day} and it's celebrations were successfully added to database".format(day=date))

    def infer_types(self, title: str) -> List[str]:
        """Infer celebration types from title."""
        title = title.lower()

        priority_celebration_types = {
            'panny marie': 'virgin mary',
            'panna maria': 'virgin mary',
            'ježíše krista': 'jesus christ',
            'nejsvětějšího srdce ježíšova': 'jesus christ',
            'nejsvětějšího jména ježíš': 'jesus christ',
            'nejsvětější trojice': 'jesus christ',
        }

        other_celebration_types = {
            'mučednice': 'martyr',
            'mučedníka': 'martyr',
            'mučedníků': 'martyr',
            'sv.': 'saint',
            'papeže': 'pope',
            'biskupa': 'bishop',
            'opata': 'abbot',
            'kněze': 'priest',
            'učitele církve': 'doctor of the church',
            'apoštola': 'apostle',
            'apoštolů': 'apostle',
            'evangelisty': 'evangelist',
            'panny': 'virgin',
        }

        celebration_types = []
        types, title = self.get_and_replace_type(title, priority_celebration_types)
        celebration_types.extend(types)
        types, title = self.get_and_replace_type(title, other_celebration_types)
        celebration_types.extend(types)
        return celebration_types

    def get_and_replace_type(self, title: list, celebration_types: Dict[str, str]) -> Tuple[List[str], str]:
        types = []
        for keyword, celebration_type in celebration_types.items():
            if keyword in title:
                types.append(celebration_type)
                title = title.replace(keyword, '')
        return types, title
