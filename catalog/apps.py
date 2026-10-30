from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog'
    verbose_name = 'Kancionál'

    def ready(self) -> None:
        from catalog import signals

        signals.connect()
