from threading import Lock
from seguimiento_parlamentario.extraction.scrapers import (
    ChamberOfDeputiesScraper,
    SenateScraper
)
import os
import datetime as dt
from google.cloud import bigquery
from pymongo import MongoClient
from pymongo import (
    TEXT,
    ASCENDING,
)
from abc import ABC, abstractmethod

scrapers = [
    ChamberOfDeputiesScraper(),
    SenateScraper(),
]

def get_db():
    if os.getenv("SERVICE_MODE") == "gcloud":
        return BigQueryDatabase()
    if os.getenv("SERVICE_MODE") == "celery":
        return MongoDatabase()
    return None

class DataBase(ABC):
    @abstractmethod
    def init(self):
        ...

    @abstractmethod
    def find_commission(self, commission_id):
        ...
    
    @abstractmethod
    def get_commissions_ids(self):
        ...

    @abstractmethod
    def add_commissions(self, commissions):
        ...

    @abstractmethod
    def add_session(self, new_session):
        ...

    @abstractmethod
    def update_last_scraping(self, commission_id: str, new_date: dt.datetime):
        ...

    @abstractmethod
    def add_summary(self, new_summary):
        ...
    
    @abstractmethod
    def add_mindmap(self, new_mindmap):
        ...

class BigQueryDatabase(DataBase):
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:

                cls._instance = super(BigQueryDatabase, cls).__new__(cls)
                cls._instance.client = bigquery.Client(os.getenv("PROJECT_ID"))
            return cls._instance
    
    def init(self):
        """
        Initializes the database by adding commission data from scrapers.
        """
        for scraper in scrapers:
            commissions = scraper.get_commissions()
            default_date = dt.datetime.now()
            for commission in commissions:
                commission["last_update"] = default_date.isoformat()
            
            self.add_commissions(commissions)
    
    def find_commission(self, commission_id) -> list[dict]:
        query = """
SELECT *
FROM `seguimiento_parlamentario.commissions`
WHERE id = @commission_id
"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("commission_id", "STRING", commission_id)
            ]
        )

        query_job = self.client.query(query, job_config=job_config)

        rows =  query_job.result()

        [commission] = [dict(row.items()) for row in rows]

        return commission
    
    def get_commissions_ids(self):
        query = """
SELECT id
FROM `seguimiento_parlamentario.commissions`
WHERE extraction_enabled = TRUE
"""

        query_job = self.client.query(query)

        rows = query_job.result()
        ids = [row["id"] for row in rows]

        return ids
    
    def add_commissions(self, commissions):
        table_id = "seguimiento_parlamentario.commissions"

        job = self.client.load_table_from_json(commissions, table_id)
        job.result()
    
    def add_session(self, new_session):
        table_id = "seguimiento_parlamentario.sessions"

        job = self.client.load_table_from_json([new_session], table_id)
        job.result()
    
    def update_last_scraping(self, commission_id: str, new_date: dt.datetime):
        query = """
UPDATE `seguimiento_parlamentario.commissions`
SET last_update = @last_update
WHERE id = @commission_id
"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("last_update", "TIMESTAMP", new_date.isoformat()),
                bigquery.ScalarQueryParameter("commission_id", "STRING", commission_id),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)

        query_job.result()
    
    def add_summary(self, new_summary):
        table_id = "seguimiento_parlamentario.summaries"

        job = self.client.load_table_from_json([new_summary], table_id)
        job.result()
    
    def add_mindmap(self, new_mindmap):
        table_id = "seguimiento_parlamentario.mindmaps"

        job = self.client.load_table_from_json([new_mindmap], table_id)
        job.result()

class MongoDatabase(DataBase):
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
                db_url = os.getenv('MONGO_URL')

                cls._instance = super(MongoDatabase, cls).__new__(cls)
                cls._instance.client = MongoClient(db_url)
                cls._instance.db = cls._instance.client["seguimiento-parlamentario"]
            return cls._instance
    
    def init(self):
        """
        Initializes the database by adding commission data from scrapers.
        """
        for scraper in scrapers:
            commissions = scraper.get_commissions()
            default_date = dt.datetime.now().astimezone(dt.timezone.utc)
            for commission in commissions:
                commission["last_update"] = default_date
                commission["automatic_processing_enabled"] = False
                commission["extraction_enabled"] = False
            
            self.add_commissions(commissions)
        
        collection = self.db["sessions"]
        collection.create_index([('commission_id', ASCENDING)])
        collection.create_index([('date', ASCENDING)])
        collection.create_index([('transcript', TEXT)])

        collection = self.db["summaries"]
        collection.create_index([('session_id', ASCENDING)])

        collection = self.db["mindmaps"]
        collection.create_index([('session_id', ASCENDING)])

    
    def find_commission(self, commission_id: str) -> dict:
        """
        Finds commission in the database based on an id.
        
        Parameters:
            commission_id (str): Commission's id.
        
        Returns:
            Cursor: A MongoDB cursor containing the results.
        """
        commission_table = self.db["commissions"]
        rows = commission_table.find({"id": commission_id})

        [commission] = [dict(row.items()) for row in rows]
        del commission["_id"]

        return commission
    
    def get_commissions_ids(self):
        commission_table = self.db["commissions"]

        rows = commission_table.find(
            {"extraction_enabled": True},
            {"id": 1}
        )

        ids = [row["id"] for row in rows]

        return ids
    
    def add_commissions(self, commissions: list[dict]):
        """
        Inserts multiple commission records into the database.
        
        Parameters:
            new_commissions (list): A list of commission documents.
        """
        commissions_table = self.db["commissions"]
        commissions_table.insert_many(commissions)
    
    def add_session(self, new_session):
        """
        Inserts a session record into the database.
        
        Parameters:
            new_session (list): A session document.
        """
        sessions = self.db["sessions"]
        sessions.insert_many([new_session])
        del new_session["_id"]
    
    def update_last_scraping(self, commission_id: str, new_date: dt.datetime):
        commissions = self.db["commissions"]
        f = { "id": commission_id }
        v = { "$set": { "last_update": new_date } }
        commissions.update_one(f, v)

    def add_summary(self, new_summary):
        summaries = self.db["summaries"]
        summaries.insert_many([new_summary])
        del new_summary["_id"]
    
    def add_mindmap(self, new_mindmap):
        mindmaps = self.db["mindmaps"]
        mindmaps.insert_many([new_mindmap])
        del new_mindmap["_id"]