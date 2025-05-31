from seguimiento_parlamentario.core.utils import convert_datetime_in_dict
from seguimiento_parlamentario.celery.app import send_request
from google.cloud import tasks_v2
import json
import os

def create_task(endpoint, payload):
    if os.getenv("SERVICE_MODE") == "gcloud":
        create_gcloud_task(endpoint, payload)
        return
    if os.getenv("SERVICE_MODE") == "celery":
        create_celery_task(endpoint, payload)
        return

def create_gcloud_task(endpoint, payload):
    client = tasks_v2.CloudTasksClient()

    project_id = os.getenv("PROJECT_ID")
    queue = "seguimiento-parlamentario"
    location = "us-central1"
    url = os.getenv("APP_URL")

    payload = convert_datetime_in_dict(payload)

    parent = client.queue_path(project_id, location, queue)

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{url}/{endpoint}",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload).encode()
        }
    }

    response = client.create_task(parent=parent, task=task)
    print("Created task:", response.name)

def create_celery_task(endpoint, payload):
    payload = convert_datetime_in_dict(payload)
    send_request.delay(endpoint, payload)