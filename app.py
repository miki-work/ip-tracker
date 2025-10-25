from flask import Flask, request, redirect
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# Целевой URL — сюда перенаправлять после клика
TARGET_URL = "https://2gis.ru"

# Инициализация базы данных
def init_db():
    if not os.path.exists("clicks.db"):
        conn = sqlite3.connect("clicks.db")
        conn.execute("""
            CREATE TABLE clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

@app.route('/track')
def track():
    # Получаем IP
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    # Сохраняем в БД
    conn = sqlite3.connect("clicks.db")
    conn.execute(
        "INSERT INTO clicks (ip_address, timestamp) VALUES (?, ?)",
        (ip, datetime.utcnow().isoformat() + "Z")
    )
    conn.commit()
    conn.close()
    # Перенаправляем
    return redirect(TARGET_URL, code=302)

# Дополнительно: простая страница для проверки, что сервер жив
@app.route('/')
def home():
    return "IP Tracker is running. Use /track to log and redirect."

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8000)
