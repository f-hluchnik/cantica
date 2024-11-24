import requests
from feasts.models import Feast, FeastType, LiturgicalCalendar
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
        Creates entry for LiturgicalCalendar and adds Feasts and FeastTypes, which are infered from the feast title.
        """
        date = data.get('date')
        season = data.get('season')

        # Create or update LiturgicalCalendar entry
        liturgical_calendar, _ = LiturgicalCalendar.objects.update_or_create(
            date=date,
            defaults={
                'season': season,
            }
        )

        # Process celebrations
        for celebration in data.get('celebrations', []):
            slug = slugify(celebration["title"])

            # Create or update FeastType(s)
            types = self.infer_types(celebration["title"])
            feast_types = []
            for feast_type_name in types:
                feast_type, _ = FeastType.objects.get_or_create(name=feast_type_name)
                feast_types.append(feast_type)

            # Create or update Feast
            feast, _ = Feast.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': celebration.get('title'),
                }
            )
            feast.types.set(feast_types)
            feast.save()

            # Add feast to the LiturgicalCalendar entry
            liturgical_calendar.celebrations.add(feast)
        logger.info("Day {day} and it's celebrations were successfully added to database".format(day=date))
    
    def infer_types(self, title: str) -> List[str]:
        """Infer feast types from title."""
        title = title.lower()

        priority_feast_types = {
            'panny marie': 'virgin mary',
            'panna maria': 'virgin mary',
            'ježíše krista': 'jesus christ',
            'nejsvětějšího srdce ježíšova': 'jesus christ',
        }

        other_feast_types = {
            'mučednice': 'martyr',
            'mučedníka': 'martyr',
            'biskupa': 'bishop',
            'opata': 'abbot',
            'kněze': 'priest',
            'apoštola': 'apostle',
            'apoštolů': 'apostle',
            'panny': 'virgin',
        }

        feast_types = []
        types, title = self.get_and_replace_type(title, priority_feast_types)
        feast_types.extend(types)
        types, title = self.get_and_replace_type(title, other_feast_types)
        feast_types.extend(types)
        return feast_types
    
    def get_and_replace_type(self, title: list, feast_types: Dict[str, str]) -> Tuple[List[str], str]:
        types = []
        for keyword, feast_type in feast_types.items():
            if keyword in title:
                types.append(feast_type)
                title = title.replace(keyword, '')
        return types, title


