from seguimiento_parlamentario.celery_app.app import app
from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.processing.tasks import process
from seguimiento_parlamentario.extraction.scrapers import (
    SenateScraper,
    ChamberOfDeputiesScraper,
    Scraper
)
import datetime as dt

scrapers = {
    "Senado": SenateScraper(),
    "Cámara de Diputados": ChamberOfDeputiesScraper(),
}

@app.task
def extract():
    db = get_db()
    commissions = db.find_commissions({})

    today = dt.datetime.now() - dt.timedelta(hours=12)
    for commission in commissions:
        scraper: Scraper = scrapers[commission["chamber"]]
        new_sessions = scraper.process_data(
            commission_id=commission["_id"],
            start=commission["last-update"],
            end=today
        )
        db.update_last_scraping(commission["_id"], today)
        for session in new_sessions:
            process.delay(session)