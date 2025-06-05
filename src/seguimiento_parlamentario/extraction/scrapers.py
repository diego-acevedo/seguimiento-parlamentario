from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import NoSuchElementException
from seguimiento_parlamentario.core.drivers import get_driver
import datetime as dt
import re
import json
import importlib.resources as pkg_resources
from seguimiento_parlamentario import config


class Scraper(ABC):
    """
    A base class for extracting relevant information from a Parliament's website.
    This class serves as a template for web scraping operations related to parliamentary sessions.

    This class should be extended to define specific behaviors for different chambers.
    The following methods must be overridden:

    ```python
    get_sessions(commission_id, start, end)
    get_context(commission_id, session_id)
    get_attendance(commission_id, session_id)
    ```

    Attributes
    ----------
    url : str
        Base URL for the commissions data.

    Methods
    -------
    process_data(commission_id, start, end)
        Defines the overall web scraping process.
    get_sessions(commission_id, start, end)
        Retrieves session metadata within a date range.
    get_context(commission_id, session_id)
        Extracts the content details of a specific session.
    get_attendance(commission_id, session_id)
        Gathers attendance details of a session.
    """

    def __init__(self, url):
        self.url = url
        self.driver = None

    def process_data(
        self, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        """
        Scrapes the website and extracts parliamentary session data within the given date range.

        :param commission_id: The ID of the parliamentary commission.
        :type commission_id: int
        :param start: The start date of the period to scrape.
        :type start: datetime.datetime
        :param end: The end date of the period to scrape.
        :type end: datetime.datetime
        :return: A list containing session data including general info, context, and attendance.
        :rtype: list[dict]
        """
        driver = get_driver()
        sessions = self.get_sessions(driver, commission_id, start, end)
        sessions = list(
            filter(lambda s: s["start"] >= start and s["start"] <= end, sessions)
        )

        for session in sessions:
            session["context"] = self.get_context(driver, session["id"], commission_id)
            session["attendance"] = self.get_attendance(driver, session["id"], commission_id)

        driver.quit()

        return sessions

    @abstractmethod
    def get_sessions(
        self, driver, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        """
        Retrieves a list of session metadata from a given parliamentary commission within a date range.

        :param commission_id: The ID of the commission.
        :type commission_id: int
        :param start: The start date of the period.
        :type start: datetime.datetime
        :param end: The end date of the period.
        :type end: datetime.datetime
        :return: A list of session metadata.
        :rtype: list[dict]
        """
        ...

    @abstractmethod
    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Extracts contextual information from a specific session.

        :param session_id: The ID of the session.
        :type session_id: int
        :param commission_id: The ID of the commission.
        :type commission_id: int
        :return: A list containing general information of the session's content.
        :rtype: list[dict]
        """
        ...

    @abstractmethod
    def get_attendance(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Retrieves attendance information from a specific session.

        :param session_id: The ID of the session.
        :type session_id: int
        :param commission_id: The ID of the commission.
        :type commission_id: int
        :return: A list containing a session's attendees.
        :rtype: list[dict]
        """
        ...

    @abstractmethod
    def get_commissions(self) -> list[dict]:
        """
        Retrieves all commissions from a chamber of the Parliament.

        :return: A list containing all commissions.
        :rtype: list[dict]
        """
        ...


class SenateScraper(Scraper):
    """
    A scraper specialized for extracting session data from the Senate's website.

    This class extends the `Scraper` base class and provides implementation
    specific to the Senate's structure and data layout.

    Attributes
    ----------
    __url : str
        Base URL for the Senate's commission data.
    __commission_url : function
        Generates URLs for specific commissions.
    __session_url : function
        Generates URLs for specific sessions.
    """

    def __init__(self):
        super().__init__("https://www.senado.cl/actividad-legislativa/comisiones")
        self.__commission_url = lambda commission_id: f"{self.url}/{commission_id}"
        self.__session_url = (
            lambda commission_id, session_id: f"{self.url}/{commission_id}/{session_id}"
        )

    def get_sessions(
        self, driver, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        driver.get(self.__commission_url(commission_id))

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[text()='Sesiones']"))
        )

        # Move to sessions section
        button = driver.find_element(By.XPATH, "//button[text()='Sesiones']")
        ActionChains(driver).scroll_to_element(button).perform()
        button.click()

        select = Select(driver.find_element(By.ID, "legislatura"))
        values = []
        # Filter out selection option outside date range
        for option in select.options:
            match = re.search(
                r"(\d{2}/\d{2}/\d{4}) al (\d{2}/\d{2}/\d{4})", option.text
            )
            start_date = dt.datetime.strptime(match.group(1), "%d/%m/%Y").astimezone(dt.timezone.utc)
            end_date = dt.datetime.strptime(match.group(2), "%d/%m/%Y").astimezone(dt.timezone.utc)
            if (start <= end_date) and (end >= start_date):
                values.append(option.get_attribute("value"))

        sessions = []

        for value in list(set(values)):
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.ID, "legislatura").is_enabled()
            )
            select.select_by_value(value)
            while True:
                WebDriverWait(driver, 5).until(
                    lambda d: d.find_element(By.ID, "legislatura").is_enabled()
                )

                # Find next page button to handle pagination
                try:
                    next_arrow = driver.find_element(
                        By.XPATH,
                        "//a[contains(text(), 'Siguiente') and not(contains(@class, 'disabled'))]",
                    )
                    ActionChains(driver).scroll_to_element(next_arrow).perform()
                except NoSuchElementException:
                    next_arrow = None

                new_sessions = []

                table = driver.find_elements(By.XPATH, "//table//tbody//tr")

                for row in table:
                    elements = row.find_elements(By.TAG_NAME, "td")
                    if elements[0].text == "No hay resultados que coincidan con la búsqueda":
                        break
                    date = dt.datetime.strptime(
                        elements[0].text, "%d/%m/%Y"
                    ).date()
                    start_time = dt.datetime.strptime(
                        elements[2].text, "%H:%M"
                    ).time()
                    end_time = dt.datetime.strptime(
                        elements[3].text, "%H:%M"
                    ).time()
                    new_sessions.append(
                        {
                            "id": int(re.search(
                                r"/\d+/(\d+)",
                                elements[4]
                                .find_element("tag name", "a")
                                .get_attribute("href"),
                            ).group(1)),
                            "commission_id": commission_id,
                            "start": dt.datetime.combine(date, start_time).astimezone(dt.timezone.utc),
                            "finish": dt.datetime.combine(date, end_time).astimezone(dt.timezone.utc),
                        }
                    )

                sessions += new_sessions

                # Iterate until there's no more pages
                if next_arrow is None:
                    break

                next_arrow.click()
        
        return sessions

    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        driver.get(self.__session_url(commission_id, session_id))

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dynamic-content"))
        )

        details = driver.find_elements(By.CLASS_NAME, "dynamic-content")
        info = []

        for element in details:
            data = {}
            try:
                data["topic"] = element.find_element(
                    By.XPATH,
                    "./h4[contains(text(), 'Tema')]/following-sibling::p"
                ).text
            except NoSuchElementException:
                pass

            try:
                data["aspects"] = element.find_element(
                    By.XPATH,
                    "./h4[contains(text(), 'Aspectos considerados')]/following-sibling::p",
                ).text
            except NoSuchElementException:
                pass

            try:
                data["agreements"] = element.find_element(
                    By.XPATH,
                    "./h4[contains(text(), 'Acuerdos')]/following-sibling::p",
                ).text
            except NoSuchElementException:
                pass

            info.append(data)

        return info

    def get_attendance(self, driver, session_id: int, commission_id: int) -> list[dict]:
        driver.get(self.__session_url(commission_id, session_id))

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "dynamic-content"))
        )

        details = driver.find_elements(By.CLASS_NAME, "dynamic-content")
        members = set()
        guests = set()

        for element in details:
            attendees = element.find_elements(
                By.XPATH, "./h4[contains(text(), 'Integrantes')]/following-sibling::p"
            )[:-1]
            members.update(set(map(lambda a: a.text, attendees[:-1])))
            guests.add(attendees[-1].text)

        return {
            "members": list(members),
            "guests": list(guests),
        }
    
    def get_commissions(self) -> list[dict]:
        driver = get_driver()
        driver.get(self.url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='tabs__content']//div[@class='component']//a"))
        )

        commissions_content = driver.find_elements(By.XPATH, "//div[@class='tabs__content']//div[@class='component']//a")

        with pkg_resources.files(config).joinpath("yt-keywords.json").open("r", encoding="utf-8") as f:
            keywords = json.load(f)
            commissions = []
            for commission in commissions_content:
                id = re.search(r'\d+', commission.get_attribute("href")).group(0)
                name = commission.find_element(By.TAG_NAME, "span").text

                commissions.append({
                    "id": int(id),
                    "name": name,
                    "chamber": "Senado",
                    "search_keywords": keywords["Senado"][id],
                })

        driver.quit()

        return commissions


class ChamberOfDeputiesScraper(Scraper):
    """
    A scraper specialized for extracting session data from the Chamber of Deputies' website.

    This class extends the `Scraper` base class and provides implementation
    specific to the Chamber of Deputies' structure and data layout.

    Attributes
    ----------
    __url : str
        Base URL for the Chamber of Deputies' commission data.
    __commission_url : function
        Generates URLs for specific commissions.
    __results_url : function
        Generates URLs for session results.
    __attendance_url : function
        Generates URLs for attendance data.
    __month_dict : dict
        Maps Spanish month abbreviations to numerical values.
    """

    def __init__(self):
        super().__init__("https://www.camara.cl/legislacion/comisiones")
        self.__commission_url = lambda c_id: f"{self.url}/sesiones.aspx?prmID={c_id}"
        self.__results_url = (
            lambda c_id, s_id: f"{self.url}/resultado_detalle.aspx?prmId={c_id}&prmIdSesion={s_id}"
        )

        self.__attendance_url = (
            lambda c_id, s_id: f"{self.url}/asistencia.aspx?prmId={c_id}&prmIdSesion={s_id}"
        )
        self.__month_dict = {
            "ene.": 1,
            "feb.": 2,
            "mar.": 3,
            "abr.": 4,
            "may.": 5,
            "jun.": 6,
            "jul.": 7,
            "ago.": 8,
            "sep.": 9,
            "oct.": 10,
            "nov.": 11,
            "dic.": 12,
        }

    def get_sessions(
        self, driver, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        driver.get(self.__commission_url(commission_id))

        sessions = []

        for year in range(start.year, end.year + 1):
            self.__select(driver, "year", str(year))
            print(start, dt.datetime(year=year, month=1, day=1).astimezone(dt.timezone.utc))
            for month in range(
                max(start, dt.datetime(year=year, month=1, day=1).astimezone(dt.timezone.utc)).month,
                min(end, dt.datetime(year=year, month=12, day=31).astimezone(dt.timezone.utc)).month + 1,
            ):
                self.__select(driver, "mes", str(month).zfill(2))
                rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    try:
                        session_id = re.search(
                            r"prmIdSesion=(\d+)",
                            cells[10]
                            .find_element(By.TAG_NAME, "a")
                            .get_attribute("href"),
                        ).group(1)
                        date = self.__str_to_date(cells[1].text)
                        start_time = dt.datetime.strptime(
                            cells[2].text, "%H:%M"
                        ).time()
                        end_time = dt.datetime.strptime(
                            cells[3].text, "%H:%M"
                        ).time()
                        sessions.append(
                            {
                                "id": int(session_id),
                                "commission_id": commission_id,
                                "start": dt.datetime.combine(date, start_time).astimezone(dt.timezone.utc),
                                "finish": dt.datetime.combine(date, end_time).astimezone(dt.timezone.utc),
                            }
                        )
                    except NoSuchElementException:
                        continue

        return sessions

    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        driver.get(self.__results_url(commission_id, session_id))

        results = []

        rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            results.append(
                {
                    "citation": cells[0].text,
                    "result": cells[1].text,
                }
            )

        return results

    def get_attendance(self, driver, session_id: int, commission_id: int) -> list[dict]:
        driver.get(self.__attendance_url(commission_id, session_id))

        attendance = []

        attendees = driver.find_elements(By.CLASS_NAME, "integrante")

        for attendee in attendees:
            info = attendee.find_elements(By.TAG_NAME, "p")
            attendance.append(
                {
                    "name": info[0].text,
                    "status": info[1].text,
                }
            )

        return attendance
    
    def get_commissions(self) -> list[dict]:
        driver = get_driver()
        driver.get(f"{self.url}/comisiones_permanentes.aspx")

        commissions_content = driver.find_elements(By.XPATH, "//table//tbody//tr")

        commissions = []
        with pkg_resources.files(config).joinpath("yt-keywords.json").open("r", encoding="utf-8") as f:
            keywords = json.load(f)
            for commission in commissions_content:
                commission_cell = commission.find_elements(By.TAG_NAME, "td")[1]
                id = re.search(r'prmID=(\d+)', commission_cell.find_element(By.TAG_NAME, "a").get_attribute('href')).group(1)
                commissions.append({
                    "id": int(id),
                    "name": f"Comisión de {commission_cell.text}",
                    "chamber": "Cámara de Diputados",
                    "search_keywords": keywords["Cámara de Diputados"][id]
                })
        
        driver.quit()

        return commissions

    def __select(self, driver, class_name, value):
        select_element = driver.find_element(
            By.XPATH, f"//div[@class='{class_name}']//select"
        )
        select = Select(select_element)
        select.select_by_value(value)

    def __str_to_date(self, date_str):
        elems = date_str.split(" ")
        return dt.date(int(elems[2]), self.__month_dict[elems[1]], int(elems[0]))
