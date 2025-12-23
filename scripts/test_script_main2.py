import os
import time
import logging
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import psycopg2
from datetime import datetime, timedelta
from check_and_send_alerts import check_thresholds
import pickle

def save_cookies(driver, path):
    with open(path, 'wb') as filehandler:
        pickle.dump(driver.get_cookies(), filehandler)

def load_cookies(driver, path):
    import os
    if os.path.exists(path):
        with open(path, 'rb') as cookiesfile:
            cookies = pickle.load(cookiesfile)
            for cookie in cookies:
                # Selenium requires expiry to be int, not float
                if isinstance(cookie.get('expiry', None), float):
                    cookie['expiry'] = int(cookie['expiry'])
                try:
                    driver.add_cookie(cookie)
                except Exception:
                    pass

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

    # 📅 Set target date to **yesterday**
    yesterday = datetime.now().date() - timedelta(days=1)

    # ✅ Skip if threshold already exists for yesterday
    cur.execute("SELECT 1 FROM daily_thresholds WHERE date = %s", (yesterday,))
    if cur.fetchone():
        logging.info(f"ℹ️ Daily threshold already exists for {yesterday}")
        cur.close()
        conn.close()
        return

    # ✅ Ensure enough records exist (e.g. 30+)
    cur.execute("""
        SELECT COUNT(*) FROM user_activity_log
        WHERE DATE(timestamp) = %s
    """, (yesterday,))
    record_count = cur.fetchone()[0]

    if record_count < 30:
        logging.warning(f"⚠️ Not enough user activity data for {yesterday}: only {record_count} records")
        cur.close()
        conn.close()
        return

    # 📊 Fetch min, max, avg
    cur.execute("""
        SELECT 
            MIN(active_users),
            MAX(active_users),
            AVG(active_users)    
        FROM user_activity_log
        WHERE DATE(timestamp) = %s
    """, (yesterday,))
    result = cur.fetchone()

    if result and result[0] is not None and result[1] is not None:
        daily_low, daily_high, daily_avg = result
        cur.execute("""
            INSERT INTO daily_thresholds (date, daily_high, daily_low, daily_avg)
            VALUES (%s, %s, %s, %s)
        """, (yesterday, daily_high, daily_low, daily_avg))
        conn.commit()
        logging.info(f"✅ Inserted threshold for {yesterday}: low={daily_low}, high={daily_high}, avg={daily_avg}")
    else:
        logging.warning(f"⚠️ No usable data found for {yesterday}")

    cur.close()
    conn.close()


def calculate_all_weekly_thresholds():
    conn = connect_db()
    cur = conn.cursor()

    # Get earliest date from daily_thresholds
    cur.execute("SELECT MIN(DATE(date)) FROM daily_thresholds")
    start_date = cur.fetchone()[0]

    if not start_date:
        logging.warning("⚠️ No data in daily_thresholds table.")
        cur.close()
        conn.close()
        return

    # Align to Monday
    start_date = start_date - timedelta(days=start_date.weekday())
    today = datetime.now().date()

    current = start_date
    while True:
        monday = current
        sunday = monday + timedelta(days=6)

        # ✅ Skip if the week hasn't ended yet (Sunday in future)
        if sunday >= today:
            logging.info(f"🟡 Week {monday} to {sunday} not completed yet. Skipping.")
            break

        # ✅ Skip if already calculated
        cur.execute("SELECT 1 FROM weekly_thresholds WHERE week_start = %s", (monday,))
        if cur.fetchone():
            logging.info(f"⏭️ Weekly threshold for {monday} already exists. Skipping.")
            current += timedelta(days=7)
            continue

        # ✅ Ensure at least one row exists in daily_thresholds for this week
        cur.execute("""
            SELECT COUNT(*) FROM daily_thresholds
            WHERE DATE(date) BETWEEN %s AND %s
        """, (monday, sunday))
        row_count = cur.fetchone()[0]

        if row_count == 0:
            logging.info(f"⏸️ Week {monday} to {sunday} has no data in daily_thresholds. Skipping.")
            current += timedelta(days=7)
            continue

        # ✅ Calculate from available data
        cur.execute("""
            SELECT MAX(daily_high), MIN(daily_low)
            FROM daily_thresholds
            WHERE DATE(date) BETWEEN %s AND %s
        """, (monday, sunday))
        result = cur.fetchone()

        if result and result[0] is not None:
            weekly_high, weekly_low = result

            HARDCODED_MAX = 10
            HARDCODED_MIN = 40

            if weekly_high > HARDCODED_MAX:
                logging.warning(f"🚨 Weekly high ({weekly_high}) > max ({HARDCODED_MAX}) [{monday}]")
            if weekly_low < HARDCODED_MIN:
                logging.warning(f"🚨 Weekly low ({weekly_low}) < min ({HARDCODED_MIN}) [{monday}]")

            cur.execute("""
                INSERT INTO weekly_thresholds (week_start, week_end, weekly_high, weekly_low)
                VALUES (%s, %s, %s, %s)
            """, (monday, sunday, weekly_high, weekly_low))
            conn.commit()
            logging.info(f"✅ Inserted weekly threshold for {monday} (based on {row_count} day(s))")
        else:
            logging.warning(f"⚠️ No usable data to insert for week {monday} to {sunday}")

        current += timedelta(days=7)

    cur.close()
    conn.close()

def start_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless=new")  # Enable stable headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=options)


def main():
    last_daily_check = None
    last_weekly_check = None
    cycle_count = 0

    logging.info("🟢 Starting continuous GA4 monitoring...")

    COOKIES_PATH = "config/cookies.pkl"
    driver = start_browser()
    driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")
    time.sleep(5)  # Let the page load

    # Try to load cookies and refresh
    try:
        load_cookies(driver, COOKIES_PATH)
        driver.refresh()
        time.sleep(5)
    except Exception as e:
        logging.warning(f"Could not load cookies: {e}")

    # If still not logged in, prompt for manual login
    if "accounts.google.com" in driver.current_url or "ServiceLogin" in driver.current_url:
        logging.info("Manual login required. Please log in within 60 seconds...")
        time.sleep(60)  # Give you time to log in manually
        save_cookies(driver, COOKIES_PATH)
        logging.info("Cookies saved for future sessions.")

    # --- Main monitoring loop ---
    while True:
        try:
            user_count = fetch_user_count(driver)
            if user_count is not None:
                insert_into_db(user_count)
                check_thresholds()

                now = datetime.now()
                if last_daily_check is None or last_daily_check != now.date():
                    calculate_daily_threshold()
                    last_daily_check = now.date()

                # Run weekly threshold check daily
                if last_weekly_check is None or last_weekly_check != now.date():
                    calculate_all_weekly_thresholds()
                    last_weekly_check = now.date()
            else:
                logging.warning("⚠️ Could not fetch user count.")

            cycle_count += 1

            if cycle_count >= 100:  # Restart browser every ~8.3 hours
                driver.quit()
                logging.info("🔁 Restarting Chrome browser after 100 cycles.")
                driver = start_browser()
                driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")
                time.sleep(60)
                cycle_count = 0

        except Exception as e:
            logging.error(f"❌ Error during main loop: {e}")
            driver.quit()
            logging.info("🔁 Restarting browser due to crash.")
            driver = start_browser()
            driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")
            time.sleep(60)

        logging.info("⏳ Sleeping for 5 minutes...")
        time.sleep(300)






if __name__ == "__main__":
    main()

 
# this code is running and working
