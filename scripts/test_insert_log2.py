import os
import time
import logging
import pickle
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import psycopg2
from datetime import datetime, timedelta

# Load environment variables
load_dotenv(dotenv_path='config/.env')

# Setup logging
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

def fetch_user_count(driver):
    try:
        wait = WebDriverWait(driver, 30)
        xpath = "//div[contains(., 'Active users in last 30 minutes')]/following-sibling::div[contains(@class, 'counter')]"
        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        user_count = int(element.text.strip().replace(',', ''))
        logging.info(f"✅ Extracted user count: {user_count}")
        return user_count
    except Exception as e:
        driver.save_screenshot("logs/fetch_user_count_error.png")
        logging.error(f"❌ Failed to extract user count: {e}")
        return None

def insert_into_db(user_count):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_activity_log (timestamp, active_users) VALUES (%s, %s)",
            (datetime.now(), user_count)
        )
        conn.commit()
        cur.close()
        conn.close()
        logging.info(f"✅ Inserted user count into DB: {user_count}")
    except Exception as e:
        logging.error(f"❌ Database insert failed: {e}")

def calculate_daily_threshold():
    conn = connect_db()
    cur = conn.cursor()
    today = datetime.now().date()
    cur.execute("SELECT 1 FROM daily_thresholds WHERE date = %s", (today,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return
    cur.execute("""
        SELECT MAX(active_users), MIN(active_users), AVG(active_users)
        FROM user_activity_log
        WHERE DATE(timestamp) = %s
    """, (today,))
    result = cur.fetchone()
    if result and result[0] is not None:
        cur.execute("""
            INSERT INTO daily_thresholds (date, daily_high, daily_low, daily_avg)
            VALUES (%s, %s, %s, %s)
        """, (today, *result))
        conn.commit()
        logging.info(f"✅ Inserted daily threshold for {today}")
    cur.close()
    conn.close()

def calculate_weekly_threshold():
    conn = connect_db()
    cur = conn.cursor()
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    cur.execute("SELECT 1 FROM weekly_thresholds WHERE week_start = %s", (monday,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return
    cur.execute("""
        SELECT MAX(active_users), MIN(active_users)
        FROM user_activity_log
        WHERE DATE(timestamp) BETWEEN %s AND %s
    """, (monday, sunday))
    result = cur.fetchone()
    if result and result[0] is not None:
        cur.execute("""
            INSERT INTO weekly_thresholds (week_start, week_end, weekly_high, weekly_low)
            VALUES (%s, %s, %s, %s)
        """, (monday, sunday, *result))
        conn.commit()
        logging.info(f"✅ Inserted weekly threshold for week {monday} to {sunday}")
    cur.close()
    conn.close()

def load_cookies(driver, cookies_path="config/cookies.pkl"):
    if not os.path.exists(cookies_path):
        raise FileNotFoundError(f"Cookies file not found at {cookies_path}")
    with open(cookies_path, "rb") as f:
        cookies = pickle.load(f)
    driver.get("https://google.com")
    time.sleep(3)
    for cookie in cookies:
        if 'sameSite' in cookie:
            del cookie['sameSite']
        driver.add_cookie(cookie)
    logging.info("🍪 Cookies loaded successfully.")

def main():
    last_daily_check = None
    last_weekly_check = None

    logging.info("🟢 Starting continuous GA4 monitoring...")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    service = Service('./chromedriver.exe')  # Adjust path if needed

    driver = webdriver.Chrome(service=service, options=options)

    try:
        # Load cookies first to skip login
        driver.get("https://analytics.google.com/")
        time.sleep(5)
        load_cookies(driver)
        driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")
        logging.info("🌐 GA4 Realtime URL opened using saved cookies")

        while True:
            user_count = fetch_user_count(driver)
            if user_count is not None:
                insert_into_db(user_count)
                now = datetime.now()

                if last_daily_check is None or last_daily_check != now.date():
                    calculate_daily_threshold()
                    last_daily_check = now.date()

                if now.weekday() == 0 and (last_weekly_check is None or last_weekly_check != now.isocalendar()[1]):
                    calculate_weekly_threshold()
                    last_weekly_check = now.isocalendar()[1]

            else:
                logging.warning("⚠️ Could not fetch user count.")
            logging.info("⏳ Sleeping for 5 minutes...")
            time.sleep(300)
    except Exception as e:
        logging.error(f"❌ Script crashed: {e}")
    finally:
        driver.quit()
        logging.info("🔴 Browser closed. Monitoring stopped.")

if __name__ == "__main__":
    main()
