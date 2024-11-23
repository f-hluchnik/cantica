import requests
from feasts.models import Feast, FeastType
from datetime import datetime
from django.core.cache import cache
from django.utils.text import slugify
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiturgyAPIClient():
    """Fetch today's liturgical calendar data and update database."""

    API_URL = "http://calapi.inadiutorium.cz/api/v0/cs/calendars/czech/today"

    def fetch_today(self, *args, **kwargs):
        today = datetime.now().date()
        todays_feasts = cache.get('today_feasts')
        if todays_feasts is not None:
            return todays_feasts
        response = requests.get(self.API_URL)
        response.raise_for_status()
        data = response.json()
        feast_slugs = self.update_database(data)
        cache.set('today_feasts', feast_slugs, timeout=3 * 60 * 60)
        return feast_slugs
        
    def update_database(self, data):
        today = datetime.strptime(data["date"], "%Y-%m-%d").date()
        feast_slugs = []

        for celebration in data.get("celebrations", []):
            slug = slugify(celebration["title"])
            feast_slugs.append(slug)

            # Create or update FeastType(s)
            types = self.infer_types(celebration["title"])
            feast_types = []
            for feast_type_name in types:
                feast_type, _ = FeastType.objects.get_or_create(name=feast_type_name)
                feast_types.append(feast_type)

            # Create or update Feast
            feast, _ = Feast.objects.update_or_create(
                slug=slug,
                date=today,
                name=celebration["title"],
                degree=celebration["rank"],
                # defaults={
                #     "colour": celebration["colour"],
                # }
            )
            feast.types.set(feast_types)
            feast.save()

        print("Successfully fetched today's feast data.")
        return feast_slugs

    def infer_types(self, title):
        """Infer feast types from title."""
        types = []
        if "mučednice" in title.lower() or "mučedníka" in title.lower():
            types.append("martyr")
        if "panny marie" in title.lower():
            types.append("panny marie")
        elif "panny" in title.lower():
            types.append("virgin")
        if "biskupa" in title.lower():
            types.append("bishop")
        if "opata" in title.lower():
            types.append("abbot")
        return types
