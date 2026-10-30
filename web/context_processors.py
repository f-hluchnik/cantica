from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict:
    return {'umami_website_id': settings.UMAMI_WEBSITE_ID}
