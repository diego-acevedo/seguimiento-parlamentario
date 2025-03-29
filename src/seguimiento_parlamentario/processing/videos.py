from seguimiento_parlamentario.core.db import MongoDatabase
from youtube_transcript_api import YouTubeTranscriptApi
import datetime as dt
import requests
import os
import re
import unicodedata
from seguimiento_parlamentario.core.exceptions import (
    YouTubeVideoNotFoundError,
)

class VideoProcessor:
    """
    Base class for processing YouTube videos of parliamentary sessions.
    
    Attributes:
        channel_id (str): The corresponding YouTube channel ID.
        session_type (str): The type of session (e.g., "Comision").
    """
    def __init__(self, channel_id, session_type):
        self.channel_id = channel_id
        self.session_type = session_type

    def get_transcription_from_yt(self, session: dict) -> dict:
        """
        Retrieves the transcription of a YouTube video based on a parliamentary session.
        
        Parameters:
            session (dict): Information about the parliamentary session.
        
        Returns:
            dict: Session data with the transcript added.
        
        Raises:
            YouTubeVideoNotFoundError: If no matching video is found.
        """
        [commission] = MongoDatabase().find_commissions({
            "_id": session["commission_id"]
        })
        
        # Performs a YouTube search for videos matching the session
        response = requests.get('https://www.googleapis.com/youtube/v3/search', params={
            'part': 'snippet',
            'channelId': self.channel_id,
            "publishedAfter": self.__yt_date(session["date"], session["start"]),
            "publishedBefore": self.__yt_date(session["date"], session["start"], delta=1),
            "type": "video",
            "q": f"{self.session_type} {" ".join(commission["search-keywords"])}",
            'key': os.getenv('YT_API_KEY'),
        })
        
        # Raise an exception if no videos are found
        if response.json()["pageInfo"]["totalResults"] == 0:
            raise YouTubeVideoNotFoundError(session_id=session["_id"])

        # Manage case of multiple matches
        video_match = None
        for video in response.json()["items"]:
            if self.check_title(video["snippet"]["title"], session["start"]):
                video_match = video
                break

        if video_match is None:
            raise YouTubeVideoNotFoundError(session_id=session["_id"])

        # Retrieve the video ID and extract the transcript
        video_id = video_match["id"]["videoId"]
        captions = YouTubeTranscriptApi().fetch(video_id, languages=('es', ), preserve_formatting=True)
        transcript = ' '.join(map(lambda x: x.text, captions))

        session["transcript"] = transcript

        return session

    def __yt_date(self, date: dt.date, time: dt.time, delta: int = 0) -> str:
        combined_datetime = dt.datetime.combine(date, time) + dt.timedelta(days=delta)

        return combined_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def check_title(self, title: str, time: dt.time) -> bool:
        """
        Abstract method to verify if a video's title matches the session.
        Must be implemented in subclasses.

        Parameters:
            title (str): The video's title.
            time (datetime.time): The session start time.
        
        Returns:
            bool: True if the title matches.
        """
        return False


class SenateVideoProcessor(VideoProcessor):
    """
    Class for processing Senate session videos.
    """
    def __init__(self):
        super().__init__(
            channel_id="UC4GJ43VNn4AYfiYa0RBCHQg",
            session_type="Comision"
        )

    def check_title(self, title: str, time: dt.time) -> bool:
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        pattern = r"^Comision .* - \d{1,2} de [a-zA-Z]+ \d{4}$"

        return bool(re.match(pattern, normalized_title))
    
class ChamberOfDeputiesVideoProcessor(VideoProcessor):
    """
    Class for processing Chamber of Deputies session videos.
    """
    def __init__(self):
        super().__init__(
            channel_id="UCYd5k2TyOyOmUJNx0SH17KA",
            session_type="Comision"
        )
    
    def check_title(self, title: str, time: dt.time) -> bool:
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        keep, exclude = ("am", "pm") if time < dt.time(hour=12, minute=0) else ("pm", "am")
        pattern = rf"^Comision .*(?: /{keep})?(?<!/{exclude})/ \d{'{1,2}'} [a-z]+ \d{'{4}'}$"

        return bool(re.match(pattern, normalized_title))
