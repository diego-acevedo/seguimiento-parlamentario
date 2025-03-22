from celery import Celery
from celery.schedules import crontab
import requests
import os

app = Celery("tasks", broker=os.getenv("AMQP_URL"))


@app.task
def send_request(endpoint, payload):
    requests.post(url=f"{os.getenv('APP_URL')}/processing/{endpoint}", json=payload)


app.conf.beat_schedule = {
    "extract-periodically": {
        "task": "seguimiento_parlamentario.celery.app.send_request",
        "schedule": crontab(minute=0, hour=2, day_of_week="2-6"),
        "args": ["trigger", {}],
    }
}
