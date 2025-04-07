from seguimiento_parlamentario.celery_app.app import app
from seguimiento_parlamentario.core.db import MongoDatabase
from seguimiento_parlamentario.processing.videos import get_video_transcript
from seguimiento_parlamentario.core.exceptions import YouTubeVideoNotFoundError

@app.task
def process(session: dict):
    print("Processing")
    session_with_transcript = get_transcript(session)
    session_with_summary = summarize(session_with_transcript)

    MongoDatabase().add_sessions([session_with_summary])

def get_transcript(session: dict) -> dict:
    try:
        return get_video_transcript(session)
    except YouTubeVideoNotFoundError as e:
        print(e.message)
        return session

def summarize(x: dict) -> dict:
    return x