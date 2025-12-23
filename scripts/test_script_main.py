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
        # Updated XPath based on working element from Chrome DevTools
        xpath = "//div[contains(., 'Active users in last 30 minutes')]/following-sibling::div[contains(@class, 'counter')]"
        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        user_count = int(element.text.strip().replace(',', ''))
        logging.info(f"✅ Extracted user count: {user_count}")
        return user_count
    except Exception as e:
        driver.save_screenshot("logs/fetch_user_count_error.png")  # Screenshot for debugging
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

    # Check if today's threshold is already recorded
    cur.execute("SELECT 1 FROM daily_thresholds WHERE date = %s", (today,))
    if cur.fetchone():
        logging.info(f"ℹ️ Daily threshold already exists for {today}")
        cur.close()
        conn.close()
        return

    # Get today's min and max from user_activity_log
    cur.execute("""
        SELECT 
            MIN(active_users),
            MAX(active_users),
            AVG(active_users)    
        FROM user_activity_log
        WHERE DATE(timestamp) = %s
    """, (today,))
    result = cur.fetchone()

    if result and result[0] is not None and result[1] is not None:
        daily_low, daily_high = result
        cur.execute("""
            INSERT INTO daily_thresholds (date, daily_high, daily_low, daily_avg)
            VALUES (%s, %s, %s, %s)
        """, (today, daily_low, daily_high))
        conn.commit()
        logging.info(f"✅ Inserted daily threshold for {today}: low={daily_low}, high={daily_high}")
    else:
        logging.warning(f"⚠️ No user activity found for {today}")

    cur.close()
    conn.close()



# def calculate_daily_threshold():
#     conn = connect_db()
#     cur = conn.cursor()
#     today = datetime.now().date()

#     # Skip if already inserted
#     cur.execute("SELECT 1 FROM daily_thresholds WHERE date = %s", (today,))
#     if cur.fetchone():
#         cur.close()
#         conn.close()
#         return

#     # Find the max, min, and average from today's data in user_activity_log
#     cur.execute("""
#         SELECT 
#             MAX(active_users),
#             MIN(active_users),
#             AVG(active_users)
#         FROM user_activity_log
#         WHERE DATE(timestamp) = %s
#     """, (today,))
#     result = cur.fetchone()

#     if result and result[0] is not None:
#         cur.execute("""
#             INSERT INTO daily_thresholds (date, daily_high, daily_low, daily_avg)
#             VALUES (%s, %s, %s, %s)
#         """, (today, *result))
#         conn.commit()
#         logging.info(f"✅ Inserted daily threshold for {today}")

#     cur.close()
#     conn.close()

def calculate_weekly_threshold():
    conn = connect_db()
    cur = conn.cursor()

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    # Skip if already inserted
    cur.execute("SELECT 1 FROM weekly_thresholds WHERE week_start = %s", (monday,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return

    cur.execute("""
        SELECT MAX(daily_high), MIN(daily_low)
        FROM daily_thresholds
        WHERE DATE(date) BETWEEN %s AND %s
    """, (monday, sunday))
    result = cur.fetchone()

    if result and result[0] is not None:
        weekly_high, weekly_low = result

        # Hardcoded threshold values
        HARDCODED_MAX = 10
        HARDCODED_MIN = 40

        # Compare with hardcoded values
        if weekly_high > HARDCODED_MAX:
            logging.warning(f"🚨 Weekly high ({weekly_high}) exceeded hardcoded max ({HARDCODED_MAX})")

        if weekly_low < HARDCODED_MIN:
            logging.warning(f"🚨 Weekly low ({weekly_low}) fell below hardcoded min ({HARDCODED_MIN})")

        cur.execute("""
            INSERT INTO weekly_thresholds (week_start, week_end, weekly_high, weekly_low)
            VALUES (%s, %s, %s, %s)
        """, (monday, sunday, weekly_high, weekly_low))
        conn.commit()
        logging.info(f"✅ Inserted weekly threshold for week {monday} to {sunday}")

    cur.close()
    conn.close()



def main():
    last_daily_check = None
    last_weekly_check = None

    logging.info("🟢 Starting continuous GA4 monitoring...")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    service = Service()

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://analytics.google.com/analytics/web/#/p399777971/realtime/overview")
        logging.info("🌐 GA4 Realtime URL opened. Waiting 60 seconds for manual login...")
        time.sleep(60)  # Wait for manual login

        while True:
            user_count = fetch_user_count(driver)
            if user_count is not None:
                insert_into_db(user_count)
                check_thresholds()  # ✅ Check alert thresholds right after data insert

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

