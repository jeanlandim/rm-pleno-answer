from celery import Celery

app = Celery('realmate_challenge')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
