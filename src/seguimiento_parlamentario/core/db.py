from pymongo import MongoClient
from threading import Lock
from seguimiento_parlamentario.extraction.scrapers import (
    ChamberOfDeputiesScraper,
    SenateScraper
)
import os

scrapers = [
    ChamberOfDeputiesScraper(),
    SenateScraper(),
]

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
            self.add_commissions(scraper.get_commissions())
    
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