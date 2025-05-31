from abc import ABC, abstractmethod
from seguimiento_parlamentario.core.db import get_db
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver import ActionChains
import datetime as dt
import requests
import os
import re
import unicodedata
import ffmpeg
import numpy as np
from seguimiento_parlamentario.core.exceptions import (
    YouTubeVideoNotFoundError,
    VideoUrlNotFoundError,
)
from seguimiento_parlamentario.core.drivers import get_driver

class VideoProcessor(ABC):
    """
    Base class for processing YouTube videos of parliamentary sessions.
    
    Attributes:
        channel_id (str): The corresponding YouTube channel ID.
        session_type (str): The type of session (e.g., "Comision").
    """
    def __init__(self, channel_id, session_type, videos_website):
        self.channel_id = channel_id
        self.session_type = session_type
        self.videos_website = videos_website

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
        commission = get_db().find_commission(session["commission_id"])
        
        # Performs a YouTube search for videos matching the session
        response = requests.get('https://www.googleapis.com/youtube/v3/search', params={
            'part': 'snippet',
            'channelId': self.channel_id,
            "publishedAfter": self.__yt_date(session["start"]),
            "publishedBefore": self.__yt_date(session["start"], delta=1),
            "type": "video",
            "q": f"{self.session_type} {' '.join(commission['search_keywords'])}",
            'key': os.getenv('YT_API_KEY'),
        })
        
        # Raise an exception if no videos are found
        if response.json()["pageInfo"]["totalResults"] == 0:
            raise YouTubeVideoNotFoundError(session_id=session["id"])

        # Manage case of multiple matches
        video_match = None
        for video in response.json()["items"]:
            if self.check_title(video["snippet"]["title"], session["start"].time()):
                video_match = video
                break

        if video_match is None:
            raise YouTubeVideoNotFoundError(session_id=session["id"])

        # Retrieve the video ID and extract the transcript
        video_id = video_match["id"]["videoId"]

        ytt_api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=os.getenv("PROXY_USERNAME"),
                proxy_password=os.getenv("PROXY_PASSWORD"),
            )
        )
        captions = ytt_api.fetch(video_id, languages=('es', ), preserve_formatting=True)
        transcript = ' '.join(map(lambda x: x.text, captions))

        session["transcript"] = transcript

        return session
    
    def get_transcription_from_video(self, session: dict):
        url = self.get_video_url(session)
        audio_np = self.__extract_audio_np_from_video(url)
        transcription = self.__transcribe_audio_np(audio_np)

        return transcription
    
    @abstractmethod
    def get_video_url(self, session: dict):
        ...
    
    def __extract_audio_np_from_video(self, url: str) -> np.ndarray:
        # Use ffmpeg to extract mono, 16kHz PCM audio into raw bytes (s16le)
        process = (
            ffmpeg
            .input(url)
            .output('pipe:', format='s16le', acodec='pcm_s16le', ac=1, ar='16000')
            .run_async(pipe_stdout=True, pipe_stderr=True)
        )
        out, err = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {err.decode()}")

        # Convert raw audio bytes to NumPy int16 array, then normalize to float32
        audio = np.frombuffer(out, np.int16).astype(np.float32) / 32768.0
        return audio

    def __transcribe_audio_np(self, audio_np: np.ndarray) -> str:
        pass

    def __yt_date(self, date: dt.datetime, delta: int = 0) -> str:
        delta_datetime = date + dt.timedelta(days=delta)

        return delta_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    @abstractmethod
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
        ...


class SenateVideoProcessor(VideoProcessor):
    """
    Class for processing Senate session videos.
    """
    def __init__(self):
        super().__init__(
            channel_id="UC4GJ43VNn4AYfiYa0RBCHQg",
            session_type="Comision",
            videos_website="https://tv.senado.cl/cgi-bin/prontus_search.cgi?search_prontus=tvsenado",
        )

    def check_title(self, title: str, time: dt.time) -> bool:
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        pattern = r"^Comision .* - \d{1,2} de [a-zA-Z]+ \d{4}$"

        return bool(re.match(pattern, normalized_title))
    
    def get_video_url(self, session):
        driver = get_driver()
        driver.get(self.videos_website)

        commission = get_db().find_commission(session["commission_id"])

        WebDriverWait(driver, timeout=5).until(
            EC.presence_of_element_located((By.ID, "buscar"))
        )

        search_bar = driver.find_element(By.ID, "search_texto")
        search_bar.send_keys(' '.join(commission['search_keywords']))

        section = Select(driver.find_element(By.ID, "SECCION1"))
        section.select_by_value("7")
        
        start = driver.find_element(By.ID, "search_fechaini")
        start.send_keys(session["start"].strftime('%d/%m/%Y'))
        end = driver.find_element(By.ID, "search_fechafin")
        end.send_keys(session["finish"].strftime('%d/%m/%Y'))

        search_button = driver.find_element(By.XPATH, "//input[@value='Buscar']")
        search_button.click()

        try:
            WebDriverWait(driver, timeout=10).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except:
            raise VideoUrlNotFoundError(session["id"])

        player_url = driver.find_element(By.XPATH, "//article//a").get_attribute("href")

        driver.get(player_url)

        video_url = driver.find_element(By.CSS_SELECTOR, 'a[download]').get_attribute("href")

        driver.quit()

        return video_url
    
class ChamberOfDeputiesVideoProcessor(VideoProcessor):
    """
    Class for processing Chamber of Deputies session videos.
    """
    def __init__(self):
        super().__init__(
            channel_id="UCYd5k2TyOyOmUJNx0SH17KA",
            session_type="Comision",
            videos_website="https://www.camara.cl/prensa/television.aspx",
        )
    
    def get_video_url(self, session):
        driver = get_driver()
        driver.get(self.videos_website)

        commission = get_db().find_commission(session["commission_id"])

        tab_commissions = driver.find_element(By.ID, "tab_comisiones")
        tab_commissions.click()

        select_commission = Select(
            driver.find_element(
                By.XPATH,
                "//td[contains(., 'Permanentes:')]/following-sibling::td[1]//select"
            )
        )

        for option in select_commission.options:
            text = ''.join(char for char in unicodedata.normalize('NFD', option.text.lower()) if unicodedata.category(char) != 'Mn')
            if all(kw.lower() in text for kw in commission["search_keywords"]):
                select_commission.select_by_visible_text(option.text)
                break

        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.XPATH, "//div[@role='status']").get_attribute("aria-hidden") == "true"
        )
        
        date_input = driver.find_element(
            By.XPATH,
            "//td[contains(., 'Fecha:')]/following-sibling::td[1]//input"
        )
        date_input.send_keys(session["start"].strftime('%d/%m/%Y'))

        search_button = driver.find_element(By.XPATH, "//input[contains(@id, 'Buscar_comisiones')]")
        ActionChains(driver).scroll_to_element(search_button).perform()
        search_button.click()

        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.XPATH, "//div[@role='status']").get_attribute("aria-hidden") == "true"
        )

        results_tab = driver.find_element(By.XPATH, "//div[contains(@id, 'ResultadoBusqueda')]")
        results = results_tab.find_elements(By.CSS_SELECTOR, "article > div:has(input)")

        if len(results) > 1:
            time = "am" if session["start"].time < dt.time(hour=12, minute=0) else "pm"
            results = list(filter(lambda x: time in x.text))
        
        results[0].click()

        video_url = driver.find_element(By.ID, "btn_descargar").get_attribute("href")

        return video_url
    
    def check_title(self, title: str, time: dt.time) -> bool:
        normalized_title = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
        keep, exclude = ("am", "pm") if time < dt.time(hour=12, minute=0) else ("pm", "am")
        pattern = rf"^Comision .*(?: /{keep})?(?<!/{exclude})/( [a-zA-Z]+)? \d{'{1,2}'} [a-zA-Z]+ \d{'{4}'}$"

        return bool(re.match(pattern, normalized_title))

processors: dict[str, VideoProcessor] = {
    "Senado": SenateVideoProcessor(),
    "Cámara de Diputados": ChamberOfDeputiesVideoProcessor(),
}

def get_video_processor(session):
    commission = get_db().find_commission(session["commission_id"])
    return processors[commission["chamber"]]