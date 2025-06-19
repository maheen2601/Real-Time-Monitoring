# scripts/fetch_user_data.py

import os
import time
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import psycopg2
from datetime import datetime

# Load environment variables
load_dotenv(dotenv_path='config/.env')

# Set up logging
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def connect_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def fetch_active_users():
    try:
        # Selenium setup
        options = webdriver.ChromeOptions()
        service = Service('./chromedriver.exe')  # Adjust for your OS
        driver = webdriver.Chrome(service=service, options=options)

        # Open GA4 Realtime report URL
        realtime_url = "https://analytics.google.com/analytics/web/#/p399777971/realtime/overview"
        driver.get(realtime_url)

        print("🕒 Waiting for manual login (60 seconds)...")
        time.sleep(60)

        # 🔍 Update this XPath based on your GA4 interface
        xpath = '//*[@id="mat-tab-group-2-label-0"]/span[2]/span[1]/div/ga-viz-container/ga-metric-tab/div/div[2]/div/span'
  # Example placeholder
        element = driver.find_element(By.XPATH, xpath)
        active_users = int(element.text.strip())

        driver.quit()

        # Insert into database
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_activity_log (timestamp, active_users) VALUES (%s, %s);",
            (datetime.now(), active_users)
        )
        conn.commit()
        conn.close()

        logging.info(f"Inserted active user count: {active_users}")
        print(f"✅ Active Users Recorded: {active_users}")

    except Exception as e:
        logging.error(f"Error: {e}")
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    fetch_active_users()
