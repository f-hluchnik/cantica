# feasts/management/commands/fetch_today.py
import requests
from django.core.management.base import BaseCommand
from feasts.models import Feast, FeastType
from datetime import datetime

class Command(BaseCommand):
    help = "Fetch today's liturgical calendar data and update database."

    API_URL = "http://calapi.inadiutorium.cz/api/v0/cs/calendars/czech/today"

    def infer_types(self, title):
        """Infer feast types from title."""
        types = []
        if "mučednice" in title.lower():
            types.append("martyr")
        if "panny" in title.lower():
            types.append("virgin")
        # Add more rules as needed
        return types

    def handle(self, *args, **kwargs):
        response = requests.get(self.API_URL)
        if response.status_code != 200:
            self.stderr.write(f"Failed to fetch data: {response.status_code}")
            return

        data = response.json()
        today = datetime.strptime(data["date"], "%Y-%m-%d").date()

        for celebration in data.get("celebrations", []):
            # Create or update FeastType(s)
            types = self.infer_types(celebration["title"])
            feast_types = []
            for feast_type_name in types:
                feast_type, _ = FeastType.objects.get_or_create(name=feast_type_name)
                feast_types.append(feast_type)

            # Create or update Feast
            feast, created = Feast.objects.get_or_create(
                date=today,
                name=celebration["title"],
                degree=celebration["rank"],
                # defaults={
                #     "colour": celebration["colour"],
                # }
            )
            feast.types.set(feast_types)
            feast.save()

        self.stdout.write(self.style.SUCCESS("Successfully fetched today's feast data."))
