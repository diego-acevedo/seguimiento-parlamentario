from selenium import webdriver
from selenium.webdriver.chrome.service import Service


class WebDriver:
    _instance = None

    @staticmethod
    def get_driver():
        if WebDriver._instance is None:
            service = Service(executable_path="drivers/chromedriver.exe")
            WebDriver._instance = webdriver.Chrome(service=service)
        return WebDriver._instance

    @staticmethod
    def quit_driver():
        if WebDriver._instance:
            WebDriver._instance.quit()
            WebDriver._instance = None
