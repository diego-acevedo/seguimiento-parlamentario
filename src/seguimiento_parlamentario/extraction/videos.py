import datetime as dt
import os
import subprocess
import unicodedata
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from seguimiento_parlamentario.core.db import get_db
from seguimiento_parlamentario.core.drivers import get_driver
from seguimiento_parlamentario.core.exceptions import (
    VideoNotFoundError,
    VideoUrlNotFoundError,
)
from seguimiento_parlamentario.core.utils import normalize_text


class VideoProcessor(ABC):
    """
    Abstract base class for processing YouTube videos of parliamentary sessions.

    This class provides the common interface and shared functionality for downloading,
    processing, and transcribing parliamentary session videos from different chambers.
    """

    def __init__(self, videos_website):
        """
        Initialize the video processor with a base website URL.

        Args:
            videos_website: The website URL where the videos are stored
        """
        self.videos_website = videos_website

    def get_transcription(self, session: dict) -> dict:
        """
        Complete pipeline for retrieving and transcribing a parliamentary session video.

        This method orchestrates the entire process: finding the video URL, downloading
        the audio, splitting it into chunks, transcribing each chunk, and combining
        the results into a complete transcript.

        Args:
            session: Dictionary containing parliamentary session information

        Returns:
            Dictionary with session data enhanced with transcript and video_url

        Raises:
            VideoUrlNotFoundError: If no matching video URL is found
            VideoNotFoundError: If video download fails
        """
        video_url = self.get_video_url(session)
        audio_path = self.download_audio(video_url, f"./tmp/audios", {session["id"]})
        chunks = self.split_audio(audio_path)

        with ThreadPoolExecutor(max_workers=4) as executor:
            transcripts = list(executor.map(self.transcribe_audio, chunks))

        session["transcript"] = " ".join([x.text for x in transcripts])
        session["video_url"] = video_url

        return session

    def download_audio(self, url, output_path, session_id):
        """
        Download video from URL and convert to audio format.

        Uses aria2c for fast multi-connection downloading and ffmpeg for audio conversion.
        Automatically cleans up the original video file after conversion.

        Args:
            url: Video URL to download
            output_path: Directory path for output files
            session_id: Unique identifier for the session (used in filename)

        Returns:
            String path to the converted audio file, or None if conversion fails

        Raises:
            VideoNotFoundError: If download fails
        """
        video_file = f"{output_path}/{session_id}.mp4"
        audio_file = f"{output_path}/{session_id}.mp3"

        download_command = ["aria2c", "-x", "16", "-s", "16", "-o", video_file, url]

        try:
            _ = subprocess.run(
                download_command, check=True, capture_output=True, text=True
            )
            print("Download completed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Download failed: {e}")
            raise VideoNotFoundError(session_id)
        except FileNotFoundError:
            print("aria2c not found. Please install aria2.")
            return None

        convert_command = [
            "ffmpeg",
            "-i",
            video_file,
            "-q:a",
            "5",
            "-map",
            "a",
            audio_file,
        ]

        try:
            _ = subprocess.run(
                convert_command, check=True, capture_output=True, text=True
            )

            if os.path.exists(video_file):
                os.remove(video_file)

            return audio_file
        except subprocess.CalledProcessError as e:
            print(f"Conversion failed: {e}")
            return None
        except FileNotFoundError:
            print("ffmpeg not found. Please install ffmpeg.")
            return None

    def split_audio(self, input_file, chunk_length=10 * 60):
        """
        Split audio file into smaller chunks for efficient processing.

        Uses ffmpeg to segment the audio file into chunks of specified length
        without re-encoding to maintain quality and speed.

        Args:
            input_file: Path to the input audio file
            chunk_length: Length of each chunk in seconds (default: 600 = 10 minutes)

        Returns:
            List of file paths for the generated audio chunks
        """
        # Get filename without extension
        base, _ = os.path.splitext(input_file)
        output_pattern = f"{base}_part_%03d.mp3"

        command = [
            "ffmpeg",
            "-i",
            input_file,
            "-f",
            "segment",
            "-segment_time",
            str(chunk_length),
            "-c",
            "copy",  # no re-encoding
            output_pattern,
        ]

        subprocess.run(command, check=True)
        print(f"Audio split into chunks with pattern: {output_pattern}")

        # Return list of chunk filenames
        i = 0
        output_files = []
        while True:
            chunk_name = output_pattern % i
            if os.path.exists(chunk_name):
                output_files.append(chunk_name)
                i += 1
            else:
                break
        os.remove(input_file)
        return output_files

    def transcribe_audio(self, audio_file_path):
        """
        Transcribe an audio file using OpenAI's Whisper API.

        Sends the audio file to OpenAI's transcription service and automatically
        cleans up the audio file after processing.

        Args:
            audio_file_path: Path to the audio file to transcribe

        Returns:
            Transcription object containing the text and metadata
        """
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=120, max_retries=3)
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="es",
            )
        os.remove(audio_file_path)
        return transcript

    @abstractmethod
    def get_video_url(self, session: dict):
        """
        Retrieve the direct video URL for a parliamentary session.

        This method must be implemented by subclasses to handle the specific
        video platform and search interface for each chamber.

        Args:
            session: Dictionary containing session information

        Returns:
            String URL for the video download
        """
        ...


class SenateVideoProcessor(VideoProcessor):
    """
    Specialized video processor for Senate session videos.

    This class implements video URL retrieval from the Senate's TV platform,
    handling their specific search interface and result filtering.
    """

    def __init__(self):
        """
        Initialize the Senate video processor with the Senate TV search URL.
        """
        super().__init__(
            videos_website="https://tv.senado.cl/cgi-bin/prontus_search.cgi?search_prontus=tvsenado",
        )

    def get_video_url(self, session):
        """
        Retrieve video URL from Senate TV platform for a specific session.

        Searches the Senate's video database using commission keywords and date range,
        filters results based on matching criteria, and selects the appropriate video
        based on session timing (morning vs afternoon).

        Args:
            session: Dictionary containing session information including
                    commission_id, start time, and finish time

        Returns:
            String URL for direct video download

        Raises:
            VideoUrlNotFoundError: If no matching video is found
        """
        driver = get_driver()
        driver.get(self.videos_website)

        commission = get_db().find_commission(session["commission_id"])

        WebDriverWait(driver, timeout=5).until(
            EC.presence_of_element_located((By.ID, "buscar"))
        )

        search_bar = driver.find_element(By.ID, "search_texto")
        search_bar.send_keys(" ".join(commission["search_keywords"]))

        section = Select(driver.find_element(By.ID, "SECCION1"))
        section.select_by_value("7")

        start = driver.find_element(By.ID, "search_fechaini")
        start.send_keys(session["start"].strftime("%d/%m/%Y"))
        end = driver.find_element(By.ID, "search_fechafin")
        end.send_keys(session["finish"].strftime("%d/%m/%Y"))

        search_button = driver.find_element(By.XPATH, "//input[@value='Buscar']")
        driver.execute_script("arguments[0].click();", search_button)

        try:
            WebDriverWait(driver, timeout=10).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
        except:
            raise VideoUrlNotFoundError(session["id"])

        results = driver.find_elements(By.TAG_NAME, "article")
        results = list(
            filter(
                lambda item: all(
                    normalize_text(term) in normalize_text(item.text)
                    for term in commission["search_keywords"]
                ),
                results,
            )
        )

        player_url = (
            results[-1 if session["start"].time() < dt.time(hour=12, minute=0) else 0]
            .find_element(By.TAG_NAME, "a")
            .get_attribute("href")
        )

        driver.get(player_url)

        video_url = driver.find_element(By.CSS_SELECTOR, "a[download]").get_attribute(
            "href"
        )

        driver.quit()

        return video_url


class ChamberOfDeputiesVideoProcessor(VideoProcessor):
    """
    Specialized video processor for Chamber of Deputies session videos.

    This class implements video URL retrieval from the Chamber of Deputies' TV platform,
    handling their specific commission selection interface and search functionality.
    """

    def __init__(self):
        """
        Initialize the Chamber of Deputies video processor with the Chamber's TV URL.
        """
        super().__init__(
            videos_website="https://www.camara.cl/prensa/television.aspx",
        )

    def get_video_url(self, session):
        """
        Retrieve video URL from Chamber of Deputies TV platform for a specific session.

        Navigates the Chamber's television interface, selects the appropriate commission
        based on search keywords, filters by session date, and retrieves the download URL.

        Args:
            session: Dictionary containing session information including
                    commission_id and start time

        Returns:
            String URL for direct video download
        """
        driver = get_driver()
        driver.get(self.videos_website)

        commission = get_db().find_commission(session["commission_id"])

        tab_commissions = driver.find_element(By.ID, "tab_comisiones")
        tab_commissions.click()

        select_commission = Select(
            driver.find_element(
                By.XPATH,
                "//td[contains(., 'Permanentes:')]/following-sibling::td[1]//select",
            )
        )

        for option in select_commission.options:
            text = "".join(
                char
                for char in unicodedata.normalize("NFD", option.text.lower())
                if unicodedata.category(char) != "Mn"
            )
            if all(kw.lower() in text for kw in commission["search_keywords"]):
                select_commission.select_by_visible_text(option.text)
                break

        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.XPATH, "//div[@role='status']").get_attribute(
                "aria-hidden"
            )
            == "true"
        )

        date_input = driver.find_element(
            By.XPATH, "//td[contains(., 'Fecha:')]/following-sibling::td[1]//input"
        )
        date_input.send_keys(session["start"].strftime("%d/%m/%Y"))

        search_button = driver.find_element(
            By.XPATH, "//input[contains(@id, 'Buscar_comisiones')]"
        )
        ActionChains(driver).scroll_to_element(search_button).perform()
        driver.execute_script("arguments[0].click();", search_button)

        WebDriverWait(driver, 10).until(
            lambda x: x.find_element(By.XPATH, "//div[@role='status']").get_attribute(
                "aria-hidden"
            )
            == "true"
        )

        results_tab = driver.find_element(
            By.XPATH, "//div[contains(@id, 'ResultadoBusqueda')]"
        )
        results = results_tab.find_elements(By.CSS_SELECTOR, "article > div:has(input)")
        results = list(
            filter(
                lambda item: all(
                    normalize_text(term) in normalize_text(item.text)
                    for term in commission["search_keywords"]
                ),
                results,
            )
        )

        results[
            -1 if session["start"].time() < dt.time(hour=12, minute=0) else 0
        ].click()

        video_url = driver.find_element(By.ID, "btn_descargar").get_attribute("href")

        return video_url


processors: dict[str, VideoProcessor] = {
    "Senado": SenateVideoProcessor(),
    "Cámara de Diputados": ChamberOfDeputiesVideoProcessor(),
}


def get_video_processor(session):
    """
    Factory function to get the appropriate video processor for a session.

    Determines which chamber the session belongs to and returns the corresponding
    video processor instance.

    Args:
        session: Dictionary containing session information with commission_id

    Returns:
        VideoProcessor instance appropriate for the session's chamber
    """
    commission = get_db().find_commission(session["commission_id"])
    return processors[commission["chamber"]]
