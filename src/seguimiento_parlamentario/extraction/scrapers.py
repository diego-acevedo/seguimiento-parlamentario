import datetime as dt
import importlib.resources as pkg_resources
import json
import re
from abc import ABC, abstractmethod

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from seguimiento_parlamentario import config
from seguimiento_parlamentario.core.drivers import get_driver
from seguimiento_parlamentario.core.utils import get_timezone


TZ = get_timezone()


class Scraper(ABC):
    """
    Abstract base class for extracting relevant information from Parliament websites.

    This class serves as a template for web scraping operations related to parliamentary
    sessions and provides the common interface that all chamber-specific scrapers must implement.
    """

    def __init__(self, url):
        """
        Initialize the scraper with a base URL.

        Args:
            url: Base URL for the parliament chamber's website
        """
        self.url = url
        self.driver = None

    def process_data(
        self, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        """
        Orchestrates the complete web scraping process for parliamentary session data.

        This method coordinates the extraction of sessions, context, and attendance data
        within the specified date range for a given commission.

        Args:
            commission_id: The ID of the parliamentary commission
            start: The start date of the period to scrape
            end: The end date of the period to scrape

        Returns:
            List of dictionaries containing complete session data including
            general info, context, and attendance
        """
        driver = get_driver()
        sessions = self.get_sessions(driver, commission_id, start, end)
        sessions = list(
            filter(lambda s: s["start"] >= start and s["start"] <= end, sessions)
        )

        for session in sessions:
            session["context"] = self.get_context(driver, session["id"], commission_id)
            session["attendance"] = self.get_attendance(
                driver, session["id"], commission_id
            )

        driver.quit()

        return sessions

    @abstractmethod
    def get_sessions(
        self, driver, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        """
        Retrieve session metadata from a parliamentary commission within a date range.

        Args:
            driver: Selenium WebDriver instance
            commission_id: The ID of the commission
            start: The start date of the period
            end: The end date of the period

        Returns:
            List of dictionaries containing session metadata
        """
        ...

    @abstractmethod
    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Extract contextual information from a specific parliamentary session.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the session
            commission_id: The ID of the commission

        Returns:
            List of dictionaries containing session content information
        """
        ...

    @abstractmethod
    def get_attendance(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Retrieve attendance information from a specific parliamentary session.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the session
            commission_id: The ID of the commission

        Returns:
            List of dictionaries containing session attendance data
        """
        ...

    @abstractmethod
    def get_commissions(self) -> list[dict]:
        """
        Retrieve all commissions from a chamber of Parliament.

        Returns:
            List of dictionaries containing commission information
        """
        ...


class SenateScraper(Scraper):
    """
    Specialized scraper for extracting session data from the Senate's website.

    This class implements the abstract methods from the Scraper base class
    with logic specific to the Senate's website structure and data layout.
    """

    def __init__(self):
        """
        Initialize the Senate scraper with the Senate's base URL and URL generators.
        """
        super().__init__("https://www.senado.cl/actividad-legislativa/comisiones")
        self.__commission_url = lambda commission_id: f"{self.url}/{commission_id}"
        self.__session_url = (
            lambda commission_id, session_id: f"{self.url}/{commission_id}/{session_id}"
        )

    def get_sessions(
        self, driver, commission_id: int, start: dt.datetime, end: dt.datetime
    ) -> list[dict]:
        """
        Extract session data from the Senate website for a specific commission.

        Navigates through the Senate's session interface, handles pagination,
        and filters sessions by legislative periods that overlap with the date range.

        Args:
            driver: Selenium WebDriver instance
            commission_id: The ID of the Senate commission
            start: Start date for session filtering
            end: End date for session filtering

        Returns:
            List of dictionaries containing session metadata
        """
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
            start_date = dt.datetime.strptime(match.group(1), "%d/%m/%Y").astimezone(TZ)
            end_date = dt.datetime.strptime(match.group(2), "%d/%m/%Y").astimezone(TZ)
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
                    if (
                        elements[0].text
                        == "No hay resultados que coincidan con la búsqueda"
                    ):
                        break
                    date = dt.datetime.strptime(elements[0].text, "%d/%m/%Y").date()
                    start_time = dt.datetime.strptime(elements[2].text, "%H:%M").time()
                    end_time = dt.datetime.strptime(elements[3].text, "%H:%M").time()
                    new_sessions.append(
                        {
                            "id": int(
                                re.search(
                                    r"/\d+/(\d+)",
                                    elements[4]
                                    .find_element("tag name", "a")
                                    .get_attribute("href"),
                                ).group(1)
                            ),
                            "commission_id": commission_id,
                            "start": dt.datetime.combine(date, start_time).astimezone(
                                TZ
                            ),
                            "finish": dt.datetime.combine(date, end_time).astimezone(
                                TZ
                            ),
                        }
                    )

                sessions += new_sessions

                # Iterate until there's no more pages
                if next_arrow is None:
                    break

                next_arrow.click()

        return sessions

    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Extract contextual information from a specific Senate session.

        Scrapes session details including topics, aspects considered, and agreements
        from the Senate's session detail page.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the Senate session
            commission_id: The ID of the Senate commission

        Returns:
            List of dictionaries containing session context information
        """
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
                    By.XPATH, "./h4[contains(text(), 'Tema')]/following-sibling::p"
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
        """
        Extract attendance information from a specific Senate session.

        Scrapes member and guest attendance data from the Senate's session detail page.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the Senate session
            commission_id: The ID of the Senate commission

        Returns:
            Dictionary containing lists of members and guests who attended
        """
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
        """
        Retrieve all Senate commissions with their metadata.

        Scrapes the Senate's main commissions page to extract commission IDs,
        names, and associated search keywords from configuration.

        Returns:
            List of dictionaries containing Senate commission information
        """
        driver = get_driver()
        driver.get(self.url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@class='tabs__content']//div[@class='component']//a")
            )
        )

        commissions_content = driver.find_elements(
            By.XPATH, "//div[@class='tabs__content']//div[@class='component']//a"
        )

        with (
            pkg_resources.files(config)
            .joinpath("yt-keywords.json")
            .open("r", encoding="utf-8") as f
        ):
            keywords = json.load(f)
            commissions = []
            for commission in commissions_content:
                id = re.search(r"\d+", commission.get_attribute("href")).group(0)
                name = commission.find_element(By.TAG_NAME, "span").text

                commissions.append(
                    {
                        "id": int(id),
                        "name": name,
                        "chamber": "Senado",
                        "search_keywords": keywords["Senado"][id],
                    }
                )

        driver.quit()

        return commissions


class ChamberOfDeputiesScraper(Scraper):
    """
    Specialized scraper for extracting session data from the Chamber of Deputies' website.

    This class implements the abstract methods from the Scraper base class
    with logic specific to the Chamber of Deputies' website structure and data layout.
    """

    def __init__(self):
        """
        Initialize the Chamber of Deputies scraper with URLs and utility mappings.

        Sets up URL generators for different pages and creates a mapping for
        Spanish month abbreviations to numerical values.
        """
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
        """
        Extract session data from the Chamber of Deputies website for a specific commission.

        Iterates through years and months within the date range, selecting appropriate
        time periods and extracting session information from the results table.

        Args:
            driver: Selenium WebDriver instance
            commission_id: The ID of the Chamber of Deputies commission
            start: Start date for session filtering
            end: End date for session filtering

        Returns:
            List of dictionaries containing session metadata
        """
        driver.get(self.__commission_url(commission_id))

        sessions = []

        for year in range(start.year, end.year + 1):
            self.__select(driver, "year", str(year))
            print(
                start,
                dt.datetime(year=year, month=1, day=1).astimezone(TZ),
            )
            for month in range(
                max(
                    start,
                    dt.datetime(year=year, month=1, day=1).astimezone(TZ),
                ).month,
                min(
                    end,
                    dt.datetime(year=year, month=12, day=31).astimezone(TZ),
                ).month
                + 1,
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
                        start_time = dt.datetime.strptime(cells[2].text, "%H:%M").time()
                        end_time = dt.datetime.strptime(cells[3].text, "%H:%M").time()
                        sessions.append(
                            {
                                "id": int(session_id),
                                "commission_id": commission_id,
                                "start": dt.datetime.combine(
                                    date, start_time
                                ).astimezone(TZ),
                                "finish": dt.datetime.combine(
                                    date, end_time
                                ).astimezone(TZ),
                            }
                        )
                    except NoSuchElementException:
                        continue

        return sessions

    def get_context(self, driver, session_id: int, commission_id: int) -> list[dict]:
        """
        Extract contextual information from a specific Chamber of Deputies session.

        Scrapes session results including citations and outcomes from the
        Chamber of Deputies' session results page.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the Chamber of Deputies session
            commission_id: The ID of the Chamber of Deputies commission

        Returns:
            List of dictionaries containing session results and citations
        """
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
        """
        Extract attendance information from a specific Chamber of Deputies session.

        Scrapes attendee names and their attendance status from the
        Chamber of Deputies' attendance page.

        Args:
            driver: Selenium WebDriver instance
            session_id: The ID of the Chamber of Deputies session
            commission_id: The ID of the Chamber of Deputies commission

        Returns:
            List of dictionaries containing attendee names and their status
        """
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
        """
        Retrieve all Chamber of Deputies commissions with their metadata.

        Scrapes the Chamber of Deputies' permanent commissions page to extract
        commission IDs, names, and associated search keywords from configuration.

        Returns:
            List of dictionaries containing Chamber of Deputies commission information
        """
        driver = get_driver()
        driver.get(f"{self.url}/comisiones_permanentes.aspx")

        commissions_content = driver.find_elements(By.XPATH, "//table//tbody//tr")

        commissions = []
        with (
            pkg_resources.files(config)
            .joinpath("yt-keywords.json")
            .open("r", encoding="utf-8") as f
        ):
            keywords = json.load(f)
            for commission in commissions_content:
                commission_cell = commission.find_elements(By.TAG_NAME, "td")[1]
                id = re.search(
                    r"prmID=(\d+)",
                    commission_cell.find_element(By.TAG_NAME, "a").get_attribute(
                        "href"
                    ),
                ).group(1)
                commissions.append(
                    {
                        "id": int(id),
                        "name": f"Comisión de {commission_cell.text}",
                        "chamber": "Cámara de Diputados",
                        "search_keywords": keywords["Cámara de Diputados"][id],
                    }
                )

        driver.quit()

        return commissions

    def __select(self, driver, class_name, value):
        """
        Helper method to select a value from a dropdown element.

        Args:
            driver: Selenium WebDriver instance
            class_name: CSS class name of the dropdown container
            value: Value to select from the dropdown
        """
        select_element = driver.find_element(
            By.XPATH, f"//div[@class='{class_name}']//select"
        )
        select = Select(select_element)
        select.select_by_value(value)

    def __str_to_date(self, date_str):
        """
        Convert a Spanish date string to a Python date object.

        Parses date strings in format "DD MMM. YYYY" where MMM is Spanish month abbreviation.

        Args:
            date_str: Date string in Spanish format (e.g., "15 ene. 2024")

        Returns:
            datetime.date: Parsed date object
        """
        elems = date_str.split(" ")
        return dt.date(int(elems[2]), self.__month_dict[elems[1]], int(elems[0]))
