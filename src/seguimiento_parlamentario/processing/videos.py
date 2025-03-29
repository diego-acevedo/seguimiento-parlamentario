# YouTube API -> search/list params = part(snippet), channelId, publishedAfter, publishedBefore, q 
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

channels = {
    "Senado": "UC4GJ43VNn4AYfiYa0RBCHQg",
    "Cámara de Diputados": "UCYd5k2TyOyOmUJNx0SH17KA",
}

class VideoProcessor:
    def __init__(self, channel_id, session_type):
        self.channel_id = channel_id
        self.session_type = session_type

    def get_transcription_from_yt(self, session: dict):
        [commission] = MongoDatabase().find_commissions({
            "_id": session["commission_id"]
        })
        
        response = requests.get('https://www.googleapis.com/youtube/v3/search', params={
            'part': 'snippet',
            'channelId': self.channel_id,
            "publishedAfter": self.__yt_date(session["date"], session["start"]),
            "publishedBefore": self.__yt_date(session["date"], session["start"], delta=1),
            "type": "video",
            "q": f"{self.session_type} {" ".join(commission["search-keywords"])}",
            'key': os.getenv('YT_API_KEY'),
        })

        print(response.json())
        
        # Exception if no videos are found
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

        video_id = video_match["id"]["videoId"]

        captions = YouTubeTranscriptApi().fetch(video_id, languages=('es', ), preserve_formatting=True)
        transcript = ' '.join(map(lambda x: x.text, captions))

        session["transcript"] = transcript

        return session

    def __yt_date(self, date, time, delta=0):

        combined_datetime = dt.datetime.combine(date, time) + dt.timedelta(days=delta)

        return combined_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def check_title(self, title, time):
        return False


class SenateVideoProcessor(VideoProcessor):
    def __init__(self):
        super().__init__(
            channel_id="UC4GJ43VNn4AYfiYa0RBCHQg",
            session_type="Comision"
        )

    def check_title(self, title, time):
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        pattern = r"^Comision .* - \d{1,2} de [a-zA-Z]+ \d{4}$"

        return bool(re.match(pattern, normalized_title))
    
class ChamberOfDeputiesVideoProcessor(VideoProcessor):
    def __init__(self):
        super().__init__(
            channel_id="UCYd5k2TyOyOmUJNx0SH17KA",
            session_type="Comision"
        )
    
    def check_title(self, title, time):
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        keep, exclude = ("am", "pm") if time < dt.time(hour=12, minute=0) else ("pm", "am")
        pattern = rf"^Comision .*(?: /{keep})?(?<!/{exclude})/ \d{'{1,2}'} [a-z]+ \d{'{4}'}$"

        return bool(re.match(pattern, normalized_title))
