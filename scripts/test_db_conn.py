# scripts/test_db_conn.py

import os
import psycopg2
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv(dotenv_path='config/.env')

def test_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cursor = conn.cursor()
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print(f"✅ DB connected! Current timestamp: {result[0]}")
        conn.close()
    except Exception as e:
        print(f"❌ DB connection failed: {e}")

# Ensure function runs
if __name__ == "__main__":
    test_db_connection()
