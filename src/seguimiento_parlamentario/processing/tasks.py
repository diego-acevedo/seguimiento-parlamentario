from seguimiento_parlamentario.celery_app.app import app
from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.processing.videos import get_video_processor

@app.task
def process(session: dict):
    print(f"Processing session: {session['_id']}")
    steps = [
        get_transcript,
        summarize,
    ]

    processed_session = session
    for step in steps:
        processed_session = step(processed_session)

    get_db().add_sessions([processed_session])

def get_transcript(session: dict) -> dict:
    processor = get_video_processor(session)
    try:
        print(f"Retrieving transcript from YouTube for session {session['_id']}")
        return processor.get_transcription_from_yt(session)
    except:
        print(f"No YouTube transcript found for session {session['_id']}")
    try:
        print(f"Retrieving transcript from video for session {session['_id']}")
        return processor.get_transcription_from_video(session)
    except:
        print(f"No video available for session {session['_id']}")
    return session

def summarize(x: dict) -> dict:
    return x