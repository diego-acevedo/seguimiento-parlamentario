from pymongo import MongoClient
from pymongo import (
    TEXT,
    ASCENDING,
)
from threading import Lock
from seguimiento_parlamentario.extraction.scrapers import (
    ChamberOfDeputiesScraper,
    SenateScraper
)
import os
import datetime as dt

scrapers = [
    ChamberOfDeputiesScraper(),
    SenateScraper(),
]

def get_db():
    return MongoDatabase()

class MongoDatabase:
    """
    Class for handling MongoDB connections and operations.
    
    Attributes:
        client (MongoClient): The MongoDB client instance.
        db (Database): The database instance.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                user = os.getenv('DB_USER')
                pwd = os.getenv('DB_PWD')
                host = os.getenv('DB_HOST')
                port = os.getenv('DB_PORT')

                cls._instance = super(MongoDatabase, cls).__new__(cls)
                cls._instance.client = MongoClient(f"mongodb://{user}:{pwd}@{host}:{port}/")
                cls._instance.db = cls._instance.client["seguimiento-parlamentario"]
            return cls._instance
    
    def init(self):
        """
        Initializes the database by adding commission data from scrapers.
        """
        for scraper in scrapers:
            commissions = scraper.get_commissions()
            default_date = dt.datetime.now() - dt.timedelta(weeks=2)
            for commission in commissions:
                try:
                    commission["last-update"] = default_date
                    self.add_commissions([commission])
                except:
                    print(f"Commission {commission['_id']} already exists")
        
        collection = self.db["sessions"]
        collection.create_index([('commission_id', ASCENDING)])
        collection.create_index([('date', ASCENDING)])
        collection.create_index([('transcription', TEXT)])
    
    def find_commissions(self, query: dict) -> list[dict]:
        """
        Finds commissions in the database based on a query.
        
        Parameters:
            query (dict): The query criteria.
        
        Returns:
            Cursor: A MongoDB cursor containing the results.
        """
        commissions = self.db["commissions"]
        return commissions.find(query)
    
    def add_commissions(self, new_commissions: list[dict]):
        """
        Inserts multiple commission records into the database.
        
        Parameters:
            new_commissions (list): A list of commission documents.
        """
        commissions = self.db["commissions"]
        commissions.insert_many(new_commissions)

    def find_sessions(self, query: dict) -> list[dict]:
        """
        Finds sessions in the database based on a query.
        
        Parameters:
            query (dict): The query criteria.
        
        Returns:
            Cursor: A MongoDB cursor containing the results.
        """
        sessions = self.db["sessions"]
        return sessions.find(query)

    def add_sessions(self, new_sessions: list[dict]):
        """
        Inserts multiple session records into the database.
        
        Parameters:
            new_sessions (list): A list of session documents.
        """
        sessions = self.db["sessions"]
        sessions.insert_many(new_sessions)
    
    def update_last_scraping(self, commission_id: str, new_date: dt.datetime):
        commissions = self.db["commissions"]
        f = { "_id": commission_id }
        v = { "$set": { "last-update": new_date } }
        commissions.update_one(f, v)