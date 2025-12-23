from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import time

options = webdriver.ChromeOptions()
options.add_argument(r"user-data-dir=C:\\Selenium\\ChromeProfile")  # new exclusive profile
options.add_argument("--start-maximized")
options.add_argument("--disable-popup-blocking")
options.add_argument("--no-first-run")
options.add_argument("--no-default-browser-check")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

service = Service('./chromedriver.exe')  # Make sure path is correct
driver = webdriver.Chrome(service=service, options=options)
driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")

# Stay open for test
time.sleep(10)
driver.quit()
