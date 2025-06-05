from flask import Flask, request
from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.processing.videos import get_video_processor
from seguimiento_parlamentario.extraction.scrapers import (
    SenateScraper,
    ChamberOfDeputiesScraper,
    Scraper
)
import datetime as dt
import os
from seguimiento_parlamentario.core.tasks import create_task
from seguimiento_parlamentario.core.exceptions import YouTubeVideoNotFoundError
from seguimiento_parlamentario.core.utils import convert_datetime_strings_to_datetime
from seguimiento_parlamentario.processing.summarizer import get_summarizer
from seguimiento_parlamentario.processing.mindmaps import get_mindmap
import logging
import re
import json

scrapers = {
    "Senado": SenateScraper(),
    "Cámara de Diputados": ChamberOfDeputiesScraper(),
}

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

@app.route("/extract/<int:commission_id>", methods=["POST"])
def extract(commission_id):
    db = get_db()
    commission = db.find_commission(commission_id)
    scraper: Scraper = scrapers[commission["chamber"]]
    data = request.get_json()

    today = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=12)

    start = data.get("start") if data.get("start") else commission["last_update"].astimezone(dt.timezone.utc)
    end = data.get("finish") if data.get("finish") else today

    new_sessions = scraper.process_data(
        commission_id=commission["id"],
        start=start,
        end=end
    )

    db = get_db()
    if not data.get("finish"):
        db.update_last_scraping(commission["id"], today)
    
    for session in new_sessions:
        create_task("transcript", session)

    app.logger.info(f"Extraction completed for commission {commission_id}: Found {len(new_sessions)} sessions")

    return f"Extraction completed for commission {commission_id}: Found {len(new_sessions)} sessions", 200

@app.route("/transcript", methods=["POST"])
def transcript():
    db = get_db()
    session = convert_datetime_strings_to_datetime(request.get_json())
    processor = get_video_processor(session)

    try:
        app.logger.info(f"Retrieving transcript from YouTube for session {session['id']}")
        result = processor.get_transcription_from_yt(session)
        db.add_session(result)
        if db.find_commission(session["commission_id"])["automatic_processing_enabled"]:
            create_task("summarize", result)
            create_task("mindmap", result)
        return f"Transcription found for session {session['id']}", 200
    except YouTubeVideoNotFoundError as e:
        app.logger.info(f"No YouTube transcript found for session {session['id']}")
        db.add_session(session)
        return e.message, 200

@app.route("/summarize", methods=["POST"])
def summarize():
    db = get_db()
    session = convert_datetime_strings_to_datetime(request.get_json())
    commission = db.find_commission(session["commission_id"])

    data = {
        "session": session,
        "commission": commission,
    }

    try:
        summarizer = get_summarizer(data)
        summary = summarizer.process(data)
        result = {
            "session_id": session["id"],
            "model": os.getenv("MODEL_NAME"),
            "summary": summary
        }
        db.add_summary(result)
        return f"Successfully generate summary for session {session['id']}", 200
    except Exception as err:
        app.logger.error(err)
        return f"Failed to summarize session {session['id']}", 200
    
@app.route("/mindmap", methods=["POST"])
def mindmap():
    db = get_db()
    session = convert_datetime_strings_to_datetime(request.get_json())
    commission = db.find_commission(session["commission_id"])
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"

    data = {
        "session": session,
        "commission": commission,
    }

    try:
        mindmap_generator = get_mindmap(data)
        mindmap = mindmap_generator.process(data)
        result = {
            "session_id": session["id"],
            "model": os.getenv("MODEL_NAME"),
            "mindmap": json.loads(re.search(pattern, mindmap, re.DOTALL).group(1))
        }
        db.add_mindmap(result)
        return f"Successfully generate summary for session {session['id']}", 200
    except Exception as err:
        app.logger.error(err)
        create_task("save", session)
        return f"Failed to summarize session {session['id']}", 200

@app.route("/trigger", methods=["POST"])
def trigger():
    db = get_db()
    commissions = db.get_commissions_ids()

    for commission_id in commissions:
        create_task(f"extract/{commission_id}", {})

    return f"Processing {len(commissions)} commissions", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv("PORT"))