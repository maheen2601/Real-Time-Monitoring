import os
import smtplib
import logging
import psycopg2
import requests
from dotenv import load_dotenv
from datetime import datetime
from email.mime.text import MIMEText
from datetime import timedelta
from email.mime.multipart import MIMEMultipart

# Load environment variables
load_dotenv(dotenv_path='config/.env')
log_file_path = os.path.join(os.path.dirname(__file__), '..', 'cookies.pkl')

logging.basicConfig(
    filename=log_file_path,
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

def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK")
    if not webhook_url:
        logging.error("SLACK_WEBHOOK not set in .env")
        return False
    payload = {"text": message}
    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            logging.info("✅ Slack alert sent.")
            return True
        else:
            logging.error(f"❌ Slack error: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Slack exception: {e}")
        return False

def send_email_alert(subject, message):
    try:
        email_user = os.getenv("EMAIL_USER")
        email_pass = os.getenv("EMAIL_PASS")
        recipients = os.getenv("ALERT_RECIPIENTS").split(',')

        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))

        server = smtplib.SMTP(os.getenv("EMAIL_HOST"), int(os.getenv("EMAIL_PORT")))
        server.starttls()
        server.login(email_user, email_pass)
        server.sendmail(email_user, recipients, msg.as_string())
        server.quit()

        logging.info("✅ Email alert sent.")
        return True
    except Exception as e:
        logging.error(f"❌ Email alert failed: {e}")
        return False

def log_alert_to_db(user_count, threshold_type, threshold_value, alert_type, message):
    try:
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO alert_log (user_count, threshold_type, threshold_value, alert_type, message)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_count, threshold_type, threshold_value, alert_type, message))
        conn.commit()
        cur.close()
        conn.close()
        logging.info("✅ Alert logged to database.")
    except Exception as e:
        logging.error(f"❌ DB alert logging failed: {e}")

def check_thresholds():
    HARDCODED_MAX = 425
    HARDCODED_MIN = 86
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    try:
        conn = connect_db()
        cur = conn.cursor()

        # Get latest user count
        cur.execute("SELECT active_users FROM user_activity_log ORDER BY timestamp DESC LIMIT 1")
        latest = cur.fetchone()

        if not latest:
            logging.warning("No user count data found.")
            return

        user_count = latest[0]

        # ---------- Check HIGH THRESHOLD ----------
        if user_count > HARDCODED_MAX:
            cur.execute("SELECT 1 FROM alert_log WHERE threshold_type = 'max' AND alert_date = %s", (today,))
            already_sent_today = cur.fetchone()

            cur.execute("SELECT 1 FROM alert_log WHERE threshold_type = 'max' AND alert_date = %s", (yesterday,))
            sent_yesterday = cur.fetchone()

            if not already_sent_today:
                if sent_yesterday:
                    msg = f"🔁 Reminder: Active users still high ({user_count}) > {HARDCODED_MAX} [Day 2]"
                    send_slack_alert(msg)
                    send_email_alert("[Gossip Herald] GA4 Reminder: High Traffic Continues", msg)
                else:
                    msg = f"🚨 Alert: Active users ({user_count}) exceeded max threshold ({HARDCODED_MAX})"
                    send_slack_alert(msg)
                    send_email_alert("[Gossip Herald] GA4 Alert: High Traffic", msg)

                log_alert_to_db(user_count, "max", HARDCODED_MAX, "both", msg)
            else:
                logging.info("⚠️ Max alert already sent today. Skipping.")

        # ---------- Check LOW THRESHOLD ----------
        elif user_count < HARDCODED_MIN:
            cur.execute("SELECT 1 FROM alert_log WHERE threshold_type = 'min' AND alert_date = %s", (today,))
            already_sent_today = cur.fetchone()

            cur.execute("SELECT 1 FROM alert_log WHERE threshold_type = 'min' AND alert_date = %s", (yesterday,))
            sent_yesterday = cur.fetchone()

            if not already_sent_today:
                if sent_yesterday:
                    msg = f"🔁 Reminder: Active users still low ({user_count}) < {HARDCODED_MIN} [Day 2]"
                    send_slack_alert(msg)
                    send_email_alert("[Gossip Herald] GA4 Reminder: Low Traffic Continues", msg)
                else:
                    msg = f"⚠️ Alert: Active users ({user_count}) below min threshold ({HARDCODED_MIN})"
                    send_slack_alert(msg)
                    send_email_alert("[Gossip Herald] GA4 Alert: Low Traffic", msg)

                log_alert_to_db(user_count, "min", HARDCODED_MIN, "both", msg)
            else:
                logging.info("⚠️ Min alert already sent today. Skipping.")

        else:
            logging.info("✅ User count within normal range.")

        cur.close()
        conn.close()

    except Exception as e:
        logging.error(f"❌ Error in threshold checking: {e}")
