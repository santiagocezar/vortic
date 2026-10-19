from django.apps import AppConfig


class TallerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'taller'

    def ready(self):
        import taller.signals  # noqa: F401 — conecta las señales de recálculo de prioridad
