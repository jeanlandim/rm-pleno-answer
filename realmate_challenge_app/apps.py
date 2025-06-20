from django.apps import AppConfig


class RealmateChallengeAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'realmate_challenge_app'

    def ready(self):
        import realmate_challenge_app.signals
