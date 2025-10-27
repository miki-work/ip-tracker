from flask import Flask, request, redirect, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import requests

app = Flask(__name__)

# Целевая ссылка по умолчанию
DEFAULT_TARGET_URL = "https://2gis.ru"

# Подключение к Neon PostgreSQL
DATABASE_URL = "postgresql://neondb_owner:npg_Afov3TP1JjsI@ep-shy-pine-ahtyw75v-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id SERIAL PRIMARY KEY,
                ip_address TEXT NOT NULL,
                target_url TEXT NOT NULL,
                country TEXT DEFAULT 'Unknown',
                city TEXT DEFAULT 'Unknown',
                country_code TEXT DEFAULT 'xx'
            )
        """)
        conn.commit()
    conn.close()

def get_geo_info(ip):
    """Получает страну и город по IP через бесплатный API"""
    try:
        if ip in ('127.0.0.1', 'localhost'):
            return {"country": "Local", "country_code": "xx", "city": "Dev"}

        # Попробуем получить данные
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                "country": data.get("country_name", "Unknown"),
                "country_code": data.get("country_code", "xx").lower(),
                "city": data.get("city", "Unknown")
            }
    except Exception as e:
        print(f"Geo error for {ip}: {e}")

    # Fallback, если API не ответил
    return {"country": "Unknown", "country_code": "xx", "city": "Unknown"}

@app.route('/track')
def track():
    # Получаем целевую ссылку из параметра ?url=..., иначе дефолт
    target_url = request.args.get('url', DEFAULT_TARGET_URL)
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

    # Получаем геоинформацию
    geo = get_geo_info(ip)

    # Сохраняем в БД
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO clicks (ip_address, target_url, country, city, country_code) VALUES (%s, %s, %s, %s, %s)",
            (ip, target_url, geo["country"], geo["city"], geo["country_code"])
        )
        conn.commit()
    conn.close()

    return redirect(target_url, code=302)

@app.route('/')
def home():
    return '''
    <h2>✅ IP Tracker работает!</h2>
    <p>Используй: <code>/track?url=https://example.com</code></p>
    <p>Админка: <a href="/admin">/admin</a></p>
    '''

# Красивая админ-панель
@app.route('/admin')
def admin_panel():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM clicks ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
    conn.close()

    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>IP Tracker Admin</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; background: #f9f9fb; }
            h1 { color: #2c3e50; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #f1f2f6; font-weight: 600; }
            tr:hover { background: #f8f9fa; }
            .flag { display: inline-block; width: 24px; text-align: center; font-size: 18px; }
            .time { color: #7f8c8d; font-size: 0.9em; }
            .link { color: #3498db; text-decoration: underline; }
            .link:hover { color: #2980b9; }
        </style>
    </head>
    <body>
        <h1>📊 Последние 100 кликов</h1>
        <table>
            <thead>
                <tr>
                    <th>IP</th>
                    <th>Флаг</th>
                    <th>Страна</th>
                    <th>Город</th>
                    <th>Ссылка</th>
                    <th>Время</th>
                </tr>
            </thead>
            <tbody>
    '''

    for row in rows:
        # Флаг: если код страны корректный — показываем флаг, иначе — пусто
        flag = ''
        if len(row['country_code']) == 2 and row['country_code'] != 'xx':
            flag = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in row['country_code'].upper())
        else:
            flag = '🌐'

        html += f'''
            <tr>
                <td><code>{row['ip_address']}</code></td>
                <td class="flag">{flag}</td>
                <td>{row['country']}</td>
                <td>{row['city']}</td>
                <td><a href="{row['target_url']}" class="link" target="_blank">{row['target_url']}</a></td>
                <td class="time">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        '''

    html += '''
            </tbody>
        </table>
    </body>
    </html>
    '''
    return html

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
