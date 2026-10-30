from datetime import date

from django.urls import path, register_converter

from web import api, views


class IsoDateConverter:
    regex = r'(?:19|20)\d{2}-\d{2}-\d{2}'  # bounded years: no date overflow on prev/next links

    def to_python(self, value: str) -> date:
        return date.fromisoformat(value)  # ValueError (e.g. 2027-02-30) -> no match -> 404

    def to_url(self, value: date) -> str:
        return value.isoformat()


register_converter(IsoDateConverter, 'isodate')

urlpatterns = [
    path('', views.day_page, name='today'),
    path('<isodate:day>/', views.day_page, name='day'),
    path('prilezitosti/', views.occasions_page, name='occasions'),
    path('prilezitosti/<slug:key>/', views.occasions_page, name='occasion'),
    path('o-aplikaci/', views.about_page, name='about'),
    path('api/v1/days/<isodate:day>.json', api.day_json, name='api_day'),
    path('health', views.health_check, name='health'),
    path('robots.txt', views.robots_txt, name='robots'),
    # /live is answered by web.middleware.LiveMiddleware
]
