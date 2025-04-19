from selenium import webdriver
from selenium.webdriver.chrome.service import Service

def get_driver():
    service = Service(executable_path="drivers/chromedriver.exe")
    return webdriver.Chrome(service=service)
