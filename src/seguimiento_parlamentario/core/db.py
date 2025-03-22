import os
import datetime as dt
from threading import Lock
from abc import ABC, abstractmethod

from pymongo import MongoClient, TEXT, ASCENDING
from pinecone import Pinecone
from google.cloud import firestore

from seguimiento_parlamentario.extraction.scrapers import (
    ChamberOfDeputiesScraper,
    SenateScraper,
)
from seguimiento_parlamentario.core.utils import (
    batch,
    chunk_text,
    get_timezone,
)

scrapers = [
    ChamberOfDeputiesScraper(),
    SenateScraper(),
]

TZ = get_timezone()


class DataBase(ABC):
    """
    Abstract base class that defines the interface for a database handler.

    This class specifies the core operations required for initializing,
    querying, and modifying data related to commissions, sessions,
    summaries, transcripts, and mindmaps. Concrete subclasses must implement all methods.
    """

    @abstractmethod
    def init(self):
        """
        Initialize the database, including any preloading or index setup.

        This method is intended to be called once to prepare the database
        (e.g., create indexes, load initial commission data).
        """
        pass

    @abstractmethod
    def find_commissions(self, detailed: bool = False) -> list[dict]:
        """
        Retrieve a list of commissions.

        Parameters:
            detailed (bool, optional): If 1 returns the full data, else it returns the extended version.

        Returns:
            list[dict]: The commissions' document list.
        """
        pass

    @abstractmethod
    def find_sessions(
        self, commission_id: int, year: int, month: int, detailed: bool = False
    ) -> list[dict]:
        """
        Retrieve a commission document based on its unique ID.

        Parameters:
            commission_id (int): The identifier of the sessions' commission.
            year (int): Year when the sessions took place.
            month (int): Month when the sessions took place.
            detailed (bool, optional): If 1 returns the full data, else it returns the extended version.

        Returns:
            dict: The sessions' document list.
        """
        pass

    @abstractmethod
    def find_commission(self, commission_id: int) -> dict:
        """
        Retrieve a commission document based on its unique ID.

        Parameters:
            commission_id (int): The identifier of the commission.

        Returns:
            dict: The commission document.
        """
        pass

    @abstractmethod
    def find_session(self, session_id: int, detailed: bool = False) -> dict:
        """
        Retrieve a session document based on its unique ID.

        Parameters:
            session_id (int): The identifier of the session.
            detailed (bool, optional): If 1 returns the full data, else it returns the extended version.

        Returns:
            dict: The session document.
        """
        pass

    @abstractmethod
    def find_summary(self, session_id: int) -> dict:
        """
        Retrieve a summary document associated with a specific session ID.

        Parameters:
            session_id (int): The session ID to search for.

        Returns:
            dict: The summary document.
        """
        pass

    @abstractmethod
    def find_mindmap(self, session_id: int) -> dict:
        """
        Retrieve a mindmap document associated with a specific session ID.

        Parameters:
            session_id (int): The session ID to search for.

        Returns:
            dict: The mindmap document.
        """
        pass

    @abstractmethod
    def get_commissions_ids(self) -> list[int]:
        """
        Retrieve a list of commission IDs for commissions that have
        extraction enabled.

        Returns:
            list[int]: A list of commission IDs.
        """
        pass

    @abstractmethod
    def add_commissions(self, commissions: list[dict]):
        """
        Insert one or more commission documents into the database.

        Parameters:
            commissions (list[dict]): A list of commission data.
        """
        pass

    @abstractmethod
    def add_session(self, new_session: dict):
        """
        Insert a new session document into the database.

        Parameters:
            new_session (dict): The session data to insert.
        """
        pass

    @abstractmethod
    def update_last_scraping(self, commission_id: int, new_date: dt.datetime):
        """
        Update the `last_update` field of a commission to reflect
        the most recent scraping date.

        Parameters:
            commission_id (int): The ID of the commission to update.
            new_date (datetime): The new last update datetime (UTC preferred).
        """
        pass

    @abstractmethod
    def add_summary(self, new_summary: dict):
        """
        Insert a new summary document into the database.

        Parameters:
            new_summary (dict): The summary data to insert.
        """
        pass

    @abstractmethod
    def add_mindmap(self, new_mindmap: dict):
        """
        Insert a new mindmap document into the database.

        Parameters:
            new_mindmap (dict): The mindmap data to insert.
        """
        pass

    @abstractmethod
    def update_extraction_enabled(self, commission_id: int, enabled: bool):
        """
        Updates the 'extraction_enabled' field for a specific commission.

        Parameters:
            commission_id (int): The ID of the commission to update.
            enabled (bool): The new value for the 'extraction_enabled' field.
        """
        pass

    @abstractmethod
    def update_processing_enabled(self, commission_id: int, enabled: bool):
        """
        Updates the 'automatic_processing_enabled' field for a specific commission.

        Parameters:
            commission_id (int): The ID of the commission to update.
            enabled (bool): The new value for the 'automatic_processing_enabled' field.
        """
        pass


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
                db_url = os.getenv("MONGO_URL")

                cls._instance = super(MongoDatabase, cls).__new__(cls)
                cls._instance.client = MongoClient(db_url)
                cls._instance.db = cls._instance.client["seguimiento-parlamentario"]
            return cls._instance

    def init(self):
        for scraper in scrapers:
            commissions = scraper.get_commissions()
            default_date = dt.datetime.now(tz=TZ)
            for commission in commissions:
                commission["last_update"] = default_date
                commission["automatic_processing_enabled"] = False
                commission["extraction_enabled"] = False

            self.add_commissions(commissions)

        collection = self.db["sessions"]
        collection.create_index([("commission_id", ASCENDING)])
        collection.create_index([("date", ASCENDING)])
        collection.create_index([("transcript", TEXT)])

        collection = self.db["summaries"]
        collection.create_index([("session_id", ASCENDING)])

        collection = self.db["mindmaps"]
        collection.create_index([("session_id", ASCENDING)])

    def find_commissions(self, detailed: bool = False) -> list[dict]:
        if detailed:
            result = self.db["commissions"].find({}, {"_id": 0})
        else:
            result = self.db["commissions"].find(
                {},
                {
                    "_id": 0,
                    "last_update": False,
                    "automatic_processing_enabled": False,
                    "extraction_enabled": False,
                },
            )
        return list(result)

    def find_sessions(
        self, commission_id: int, year: int, month: int, detailed: bool = False
    ) -> list[dict]:
        start_date = dt.datetime(year, month, 1)
        if month == 12:
            end_date = dt.datetime(year + 1, 1, 1)
        else:
            end_date = dt.datetime(year, month + 1, 1)

        query = {
            "commission_id": commission_id,
            "start": {
                "$gte": start_date,
                "$lt": end_date,
            },
        }

        if detailed:
            result = self.db["sessions"].find(query, {"_id": 0})
        else:
            result = self.db["sessions"].find(query, {"_id": 0, "transcript": False})

        return list(result)

    def find_commission(self, commission_id: int) -> dict:
        result = self.db["commissions"].find_one({"id": commission_id}, {"_id": 0})
        return result

    def find_session(self, session_id: int, detailed: bool = False) -> dict:
        projection = (
            {"_id": 0} if detailed else {"_id": 0, "transcript": 0, "finish": 0}
        )
        result = self.db["sessions"].find_one({"id": session_id}, projection)
        return result

    def find_summary(self, session_id: int) -> dict:
        result = self.db["summaries"].find_one({"session_id": session_id}, {"_id": 0})
        return result

    def find_mindmap(self, session_id: int) -> dict:
        result = self.db["mindmaps"].find_one({"session_id": session_id}, {"_id": 0})
        return result

    def get_commissions_ids(self) -> list[int]:
        commission_table = self.db["commissions"]

        rows = commission_table.find({"extraction_enabled": True}, {"id": 1})

        ids = [row["id"] for row in rows]

        return ids

    def add_commissions(self, commissions: list[dict]):
        commissions_table = self.db["commissions"]
        commissions_table.insert_many(commissions)

    def add_session(self, new_session: dict):
        sessions = self.db["sessions"]
        sessions.insert_many([new_session])
        del new_session["_id"]

    def update_last_scraping(self, commission_id: int, new_date: dt.datetime):
        commissions = self.db["commissions"]
        f = {"id": commission_id}
        v = {"$set": {"last_update": new_date}}
        commissions.update_one(f, v)

    def add_summary(self, new_summary: dict):
        summaries = self.db["summaries"]
        summaries.insert_many([new_summary])
        del new_summary["_id"]

    def add_mindmap(self, new_mindmap: dict):
        mindmaps = self.db["mindmaps"]
        mindmaps.insert_many([new_mindmap])
        del new_mindmap["_id"]

    def update_extraction_enabled(self, commission_id: int, enabled: bool):
        self.db["commissions"].update_one(
            {"id": commission_id}, {"$set": {"extraction_enabled": enabled}}
        )

    def update_processing_enabled(self, commission_id: int, enabled: bool):
        self.db["commissions"].update_one(
            {"id": commission_id}, {"$set": {"automatic_processing_enabled": enabled}}
        )


class FirestoreDatabase(DataBase):
    """
    Class for handling Firestore connections and operations.

    Attributes:
        client (firestore.Client): The Firestore client instance.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FirestoreDatabase, cls).__new__(cls)
                cls._instance.client = firestore.Client(
                    database=os.getenv("FIRESTORE_ID")
                )
            return cls._instance

    def init(self):
        for scraper in scrapers:
            commissions = scraper.get_commissions()
            default_date = dt.datetime.now(tz=TZ)
            for commission in commissions:
                commission["last_update"] = default_date
                commission["automatic_processing_enabled"] = False
                commission["extraction_enabled"] = False

            self.add_commissions(commissions)

    def find_commissions(self, detailed: bool = False) -> list[dict]:
        docs = self.db.collection("commissions").stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            if not detailed:
                data.pop("last_update", None)
                data.pop("automatic_processing_enabled", None)
                data.pop("extraction_enabled", None)
            results.append(data)

        return results

    def find_sessions(
        self, commission_id: int, year: int, month: int, detailed: bool = False
    ) -> list[dict]:
        start_date = dt.datetime(year, month, 1)
        if month == 12:
            end_date = dt.datetime(year + 1, 1, 1)
        else:
            end_date = dt.datetime(year, month + 1, 1)

        query = (
            self.db.collection("sessions")
            .where("commission_id", "==", commission_id)
            .where("start", ">=", start_date)
            .where("start", "<", end_date)
        )

        docs = query.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            if not detailed:
                data.pop("transcript", None)
            results.append(data)

        return results

    def find_commission(self, commission_id: int) -> dict:
        ref = (
            self.client.collection("commissions")
            .where("id", "==", commission_id)
            .limit(1)
        )
        docs = list(ref.stream())
        if not docs:
            return {}
        return docs[0].to_dict()

    def find_session(self, session_id: int, detailed: bool = False) -> dict:
        query = (
            self.client.collection("sessions").where("id", "==", session_id).limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return None
        session = docs[0].to_dict()
        if not detailed:
            session.pop("transcript", None)
        return session

    def find_summary(self, session_id: int) -> dict:
        query = (
            self.client.collection("summaries")
            .where("session_id", "==", session_id)
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return None
        return docs[0].to_dict()

    def find_mindmap(self, session_id: int) -> dict:
        query = (
            self.client.collection("mindmaps")
            .where("session_id", "==", session_id)
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return None
        return docs[0].to_dict()

    def get_commissions_ids(self) -> list[int]:
        ref = self.client.collection("commissions").where(
            "extraction_enabled", "==", True
        )
        docs = ref.stream()
        return [doc.to_dict()["id"] for doc in docs]

    def add_commissions(self, commissions: list[dict]):
        batch = self.client.batch()
        collection = self.client.collection("commissions")
        for commission in commissions:
            doc_ref = collection.document(str(commission["id"]))
            batch.set(doc_ref, commission)
        batch.commit()

    def add_session(self, new_session: dict):
        doc_ref = self.client.collection("sessions").document(str(new_session["id"]))
        if "_id" in new_session:
            del new_session["_id"]
        doc_ref.set(new_session)

    def update_last_scraping(self, commission_id: int, new_date: dt.datetime):
        doc_ref = self.client.collection("commissions").document(str(commission_id))
        doc_ref.update({"last_update": new_date})

    def add_summary(self, new_summary: dict):
        if "_id" in new_summary:
            del new_summary["_id"]
        doc_ref = self.client.collection("summaries").document(str(new_summary["id"]))
        doc_ref.set(new_summary)

    def add_mindmap(self, new_mindmap: dict):
        if "_id" in new_mindmap:
            del new_mindmap["_id"]
        doc_ref = self.client.collection("mindmaps").document(str(new_mindmap["id"]))
        doc_ref.set(new_mindmap)

    def update_extraction_enabled(self, commission_id: int, enabled: bool):
        self.db.collection("commissions").document(str(commission_id)).update(
            {"extraction_enabled": enabled}
        )

    def update_processing_enabled(self, commission_id: int, enabled: bool):
        self.db.collection("commissions").document(str(commission_id)).update(
            {"automatic_processing_enabled": enabled}
        )


class PineconeDatabase:
    """
    Class to interact with Pinecone vector database for storing
    and retrieving chunks of session transcripts.

    Attributes:
        pc (Pinecone): The Pinecone client instance.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:

                cls._instance = super(PineconeDatabase, cls).__new__(cls)
                cls._instance.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            return cls._instance

    def init(self):
        index_name = "seguimiento-parlamentario"

        if not self.pc.has_index(index_name):
            self.pc.create_index_for_model(
                name=index_name,
                cloud="aws",
                region="us-east-1",
                embed={
                    "model": "llama-text-embed-v2",
                    "field_map": {"text": "chunk_text"},
                },
            )

    def upsert_records(self, session: dict):
        """
        Splits a session's transcript into text chunks, constructs records,
        and upserts them into the Pinecone index in batches.

        Parameters:
            session (dict): A session dictionary containing at least:
                - 'transcript' (str): The full transcript text.
                - 'commission_id' (str): Commission identifier.
                - 'id' (str): Session identifier.
                - 'start' (datetime): Session start datetime.

        Behavior:
            - Chunks the transcript text using a helper function `chunk_text`.
            - Creates records with composite IDs, session and commission IDs,
              timestamp (as int), and chunk text.
            - Upserts records in batches (batch size 96) to the Pinecone index
              specified by the environment variable `PINECONE_INDEX_HOST`.
            - Uses namespace "transcript_chunks" for all records.
        """
        chunks = chunk_text(session["transcript"])
        chunks = [
            {
                "_id": f"{session['commission_id']}-{session['id']}-{i}",
                "session_id": session["id"],
                "commission_id": session["commission_id"],
                "date": int(session["start"].timestamp()),
                "chunk_text": chunk,
            }
            for i, chunk in enumerate(chunks)
        ]

        index = self.pc.Index(host=os.getenv("PINECONE_INDEX_HOST"))

        for batched_chunks in batch(chunks, 96):
            index.upsert_records(
                namespace="transcript_chunks",
                records=batched_chunks,
            )

    def retrieve_records(
        self, query: str, filters: dict = {}, top_k: int = 5
    ) -> list[dict]:
        """
        Searches the Pinecone index for transcript chunks matching the input query,
        applying optional filters and limiting results.

        Parameters:
            query (str): Text query to search against the transcript chunks.
            filters (dict, optional): Dictionary of filter conditions to apply
                on metadata fields (e.g., {'commission_id': '123'}). Defaults to empty dict.
            top_k (int, optional): Maximum number of top matches to return. Defaults to 5.

        Returns:
            list: A list of matching records containing 'session_id' and 'chunk_text'.

        Behavior:
            - Searches within the "transcript_chunks" namespace.
            - Requests only 'session_id' and 'chunk_text' fields in the results.
            - Returns the hits from the Pinecone search response.
        """
        index = self.pc.Index(host=os.getenv("PINECONE_INDEX_HOST"))

        results = index.search(
            namespace="transcript_chunks",
            query={"inputs": {"text": query}, "top_k": top_k, "filter": filters},
            fields=["session_id", "chunk_text"],
        )

        return results.result.hits


def get_db() -> DataBase:
    if os.getenv("SERVICE_MODE") == "gcloud":
        return FirestoreDatabase()
    if os.getenv("SERVICE_MODE") == "celery":
        return MongoDatabase()
    return None
