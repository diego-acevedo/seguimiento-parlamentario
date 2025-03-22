import datetime as dt
import json
import logging
import os
import re

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from seguimiento_parlamentario.core.db import get_db, PineconeDatabase
from seguimiento_parlamentario.core.exceptions import VideoNotFoundError
from seguimiento_parlamentario.core.tasks import create_task
from seguimiento_parlamentario.core.utils import (
    convert_datetime_strings_to_datetime,
    get_timezone,
)
from seguimiento_parlamentario.extraction.scrapers import (
    ChamberOfDeputiesScraper,
    Scraper,
    SenateScraper,
)
from seguimiento_parlamentario.extraction.videos import get_video_processor
from seguimiento_parlamentario.processing.mindmaps import get_mindmap
from seguimiento_parlamentario.processing.summarizer import get_summarizer

from api.types import ExtractRequest, TranscriptRequest

# FastAPI router configuration
router = APIRouter(prefix="/processing", tags=["Processing"])

# Mapping scrapers per chamber
scrapers = {
    "Senado": SenateScraper(),
    "Cámara de Diputados": ChamberOfDeputiesScraper(),
}

# Global timezone and logger
TZ = get_timezone()
logger = logging.getLogger(__name__)


@router.post("/extract/{commission_id}")
async def extract(commission_id: int, data: ExtractRequest):
    """
    Extracts new legislative sessions for a given commission.

    Args:
        commission_id (int): ID of the commission to scrape data for.
        data (ExtractRequest): Request containing optional `start` and `finish` dates.

    Returns:
        PlainTextResponse: Message indicating how many new sessions were found.
    """
    db = get_db()
    commission = db.find_commission(commission_id)
    scraper: Scraper = scrapers[commission["chamber"]]

    today = dt.datetime.now(TZ) - dt.timedelta(hours=12)

    start = (
        dt.datetime.strptime(data.get("start"), "%Y-%m-%d").astimezone(TZ)
        if data.get("start")
        else commission["last_update"].astimezone(TZ)
    )
    end = (
        dt.datetime.strptime(data.get("finish"), "%Y-%m-%d").astimezone(TZ)
        if data.get("finish")
        else today
    )

    new_sessions = scraper.process_data(
        commission_id=commission["id"], start=start, end=end
    )

    if not data.get("finish"):
        db.update_last_scraping(commission["id"], today)

    for session in new_sessions:
        create_task("transcript", session)

    logger.info(
        f"Extraction completed for commission {commission_id}: Found {len(new_sessions)} sessions"
    )

    return PlainTextResponse(
        f"Extraction completed for commission {commission_id}: Found {len(new_sessions)} sessions"
    )


@router.post("/transcript")
async def transcript(request: TranscriptRequest):
    """
    Retrieves a transcript for a given session and stores it in the database.

    Args:
        request (TranscriptRequest): Request containing session details.

    Returns:
        PlainTextResponse: Success or failure message.
    """
    db = get_db()
    session = convert_datetime_strings_to_datetime(request)
    commission = db.find_commission(session["commission_id"])
    processor = get_video_processor(session)

    try:
        logger.info(f"Retrieving transcript from YouTube for session {session['id']}")
        result = processor.get_transcription_from_yt(session)

        vector_db = PineconeDatabase()
        vector_db.upsert_records(result)

        db.add_session(result)

        if commission["automatic_processing_enabled"]:
            session_id = result["id"]
            create_task(f"summarize/{session_id}", {})
            create_task(f"mindmap/{session_id}", {})

        return PlainTextResponse(f"Transcription found for session {session['id']}")
    except VideoNotFoundError as e:
        logger.info(
            f"No YouTube transcript found for session {session['id']}: {e.message}"
        )
        return PlainTextResponse(e.message)


@router.post("/summarize/{session_id}")
async def summarize(session_id: int):
    """
    Generates a summary for a given session using an AI summarizer.

    Args:
        session_id (int): ID of the session to summarize.

    Returns:
        PlainTextResponse: Success or failure message.
    """
    db = get_db()

    session = convert_datetime_strings_to_datetime(
        db.find_session(session_id, detailed=True)
    )
    commission = db.find_commission(session["commission_id"])

    data = {"session": session, "commission": commission}

    try:
        summarizer = get_summarizer(data)
        summary = summarizer.process(data)
        result = {
            "session_id": session["id"],
            "model": os.getenv("MODEL_NAME"),
            "summary": summary,
        }
        db.add_summary(result)
        return PlainTextResponse(
            f"Successfully generated summary for session {session['id']}"
        )
    except Exception as err:
        logger.error(err)
        return PlainTextResponse(f"Failed to summarize session {session['id']}")


@router.post("/mindmap/{session_id}")
async def mindmap(session_id: int):
    """
    Generates a structured mindmap for a given session.

    Args:
        session_id (int): ID of the session to process.

    Returns:
        PlainTextResponse: Success or failure message.
    """
    db = get_db()

    session = convert_datetime_strings_to_datetime(
        db.find_session(session_id, detailed=True)
    )
    commission = db.find_commission(session["commission_id"])
    pattern = r"```(?:json)?\s*(\{.*?\})\s*```"

    data = {"session": session, "commission": commission}

    try:
        mindmap_generator = get_mindmap(data)
        mindmap = mindmap_generator.process(data)
        result = {
            "session_id": session["id"],
            "model": os.getenv("MODEL_NAME"),
            "mindmap": json.loads(re.search(pattern, mindmap, re.DOTALL).group(1)),
        }
        db.add_mindmap(result)
        return PlainTextResponse(
            f"Successfully generated mindmap for session {session['id']}"
        )
    except Exception as err:
        logger.error(err)
        return PlainTextResponse(
            f"Failed to generate mindmap for session {session['id']}"
        )


@router.post("/trigger")
async def trigger():
    """
    Triggers the extraction process for all commissions.

    Returns:
        PlainTextResponse: Message indicating how many commissions are being processed.
    """
    db = get_db()
    commissions = db.get_commissions_ids()

    for commission_id in commissions:
        create_task(f"extract/{commission_id}", {})

    return PlainTextResponse(f"Processing {len(commissions)} commissions")
