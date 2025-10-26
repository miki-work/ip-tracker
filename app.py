from flask import Flask, request, redirect
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os

app = Flask(__name__)

# Целевой URL — сюда перенаправлять после клика
TARGET_URL = "https://2gis.ru"

# Строка подключения к Neon PostgreSQL (вставь свою!)
DATABASE_URL = "postgresql://neondb_owner:npg_Afov3TP1JjsI@ep-shy-pine-ahtyw75v-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id SERIAL PRIMARY KEY,
                ip_address TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL
            )
        """)
        conn.commit()
    conn.close()

@app.route('/track')
def track():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO clicks (ip_address, timestamp) VALUES (%s, %s)",
            (ip, datetime.utcnow())
        )
        conn.commit()
    conn.close()
    return redirect(TARGET_URL, code=302)

@app.route('/')
def home():
    return "IP Tracker is running. Use /track to log and redirect."

@app.route('/view')
def view_clicks():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT ip_address, timestamp FROM clicks ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
    conn.close()

    html = "<h2>Последние 50 кликов</h2><pre style='font-size:16px;'>"
    for row in rows:
        html += f"{row['timestamp'].isoformat()} | {row['ip_address']}\n"
    html += "</pre>"
    return html

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
