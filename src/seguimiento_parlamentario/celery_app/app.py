from celery import Celery
from celery.schedules import crontab
import os

app = Celery("tasks", broker=os.getenv("AMQP_URL"))

app.conf.beat_schedule = {
    "extract-every-6-hours": {
        "task": "seguimiento_parlamentario.extraction.tasks.extract",
        "schedule": crontab(minute=0, hour="*/6")
    }
}

app.autodiscover_tasks([
    'seguimiento_parlamentario.processing.tasks',
    'seguimiento_parlamentario.extraction.tasks',
])