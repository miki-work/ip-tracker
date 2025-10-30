from flask import Flask, request, redirect, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import requests

app = Flask(__name__)

# Целевая ссылка по умолчанию
DEFAULT_TARGET_URL = "https://2gis.ru"

# ⚠️ ЗАМЕНИ ЭТУ СТРОКУ НА СВОЮ ИЗ NEON (с sslmode=require)
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
                country_code TEXT DEFAULT 'xx',
                latitude REAL,
                longitude REAL,
                timestamp TIMESTAMPTZ NOT NULL
            )
        """)
        conn.commit()
    conn.close()

def get_geo_info(ip):
    try:
        if ip in ('127.0.0.1', 'localhost', '::1'):
            return {"country": "Local", "country_code": "xx", "city": "Dev", "latitude": 0.0, "longitude": 0.0}
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=4)
        if response.status_code == 200:
            data = response.json()
            country = data.get("country_name") or "Unknown"
            city = data.get("city") or "Unknown"
            code = (data.get("country_code") or "xx").lower()
            lat = float(data.get("latitude", 0.0))
            lon = float(data.get("longitude", 0.0))
            return {
                "country": country,
                "country_code": code,
                "city": city,
                "latitude": lat,
                "longitude": lon
            }
    except Exception as e:
        pass
    return {"country": "Unknown", "country_code": "xx", "city": "Unknown", "latitude": 0.0, "longitude": 0.0}

@app.route('/track')
def track():
    target_url = request.args.get('url', DEFAULT_TARGET_URL)
    if not target_url.startswith(('http://', 'https://')):
        target_url = 'https://' + target_url

    xff = request.headers.get('X-Forwarded-For', '')
    ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
    ip = request.remote_addr

    private_prefixes = (
        '192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
        '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
        '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
        '127.', '::1', 'fe80:', 'fc00:'
    )

    for candidate in ips:
        if not any(candidate.startswith(prefix) for prefix in private_prefixes):
            ip = candidate
            break

    geo = get_geo_info(ip)

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO clicks (ip_address, target_url, country, city, country_code, latitude, longitude, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (ip, target_url, geo["country"], geo["city"], geo["country_code"], geo["latitude"], geo["longitude"], datetime.utcnow())
        )
        conn.commit()
    conn.close()

    return redirect(target_url, code=302)

@app.route('/')
def home():
    return '''
    <h2>✅ IP Tracker</h2>
    <p>Пример: <a href="/track?url=https://google.com">/track?url=https://google.com</a></p>
    <p>Админка: <a href="/admin">/admin</a> | Карта: <a href="/map">/map</a> | Яндекс Карта: <a href="/yandex-map">/yandex-map</a></p>
    '''

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
            h1, h2 { color: #2c3e50; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #f1f2f6; font-weight: 600; }
            tr:hover { background: #f8f9fa; }
            .flag { 
                font-size: 18px; 
                width: 24px; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                height: 24px; 
            }
            .time { color: #7f8c8d; font-size: 0.9em; }
            .link { color: #3498db; text-decoration: underline; }
            input[type="text"] { padding: 8px; width: 100%; max-width: 500px; margin: 5px 0; box-sizing: border-box; }
            input[type="submit"] { padding: 8px 16px; background: #3498db; color: white; border: none; cursor: pointer; margin-top: 10px; }
            input[type="submit"]:hover { background: #2980b9; }
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
                    <th>Время (UTC)</th>
                </tr>
            </thead>
            <tbody>
    '''

    for row in rows:
        cc = row['country_code']
        if len(cc) == 2 and cc != 'xx':
            flag = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in cc.upper())
        else:
            flag = '🌐'
        html += f'''
            <tr>
                <td><code>{row['ip_address']}</code></td>
                <td class="flag">{flag}</td>
                <td>{row['country']}</td>
                <td>{row['city']}</td>
                <td><a href="{row['target_url']}" class="link" target="_blank">{row['target_url']}</a></td>
                <td class="time">{row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        '''

    html += '''
            </tbody>
        </table>

        <h2>🔗 Генератор трекер-ссылок</h2>
        <form method="GET" action="/track">
            <label for="url">Введите целевую ссылку:</label><br>
            <input type="text" id="url" name="url" value="https://google.com" required>
            <br>
            <input type="submit" value="Получить трекер-ссылку">
        </form>
        <p>Пример: <code>https://ip-tracker-ijlf.onrender.com/track?url=ВАША_ССЫЛКА</code></p>
    </body>
    </html>
    '''
    return html

@app.route('/map')
def map_page():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT ip_address, country, city, latitude, longitude, timestamp FROM clicks WHERE latitude != 0 AND longitude != 0 ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
    conn.close()

    markers_js = ""
    for row in rows:
        if row['latitude'] != 0.0 and row['longitude'] != 0.0:
            markers_js += f"""
            L.marker([{row['latitude']}, {row['longitude']}]).addTo(map)
                .bindPopup("<b>{row['ip_address']}</b><br>{row['country']} — {row['city']}<br>{row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}");
            """

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>IP Tracker Map</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            body {{ margin: 0; padding: 0; }}
            #map {{ height: 100vh; width: 100%; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map').setView([0, 0], 2);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }}).addTo(map);
            {markers_js}
        </script>
    </body>
    </html>
    '''

@app.route('/yandex-map')
def yandex_map_page():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT ip_address, country, city, latitude, longitude, timestamp FROM clicks WHERE latitude != 0 AND longitude != 0 ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
    conn.close()

    markers_js = ""
    for row in rows:
        if row['latitude'] != 0.0 and row['longitude'] != 0.0:
            markers_js += f"""
            var placemark = new ymaps.Placemark([{row['latitude']}, {row['longitude']}], {{
                balloonContent: "<b>{row['ip_address']}</b><br>{row['country']} — {row['city']}<br>{row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            }});
            myMap.geoObjects.add(placemark);
            """

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>IP Tracker Yandex Map</title>
        <script src="https://api-maps.yandex.ru/2.1/?lang=ru_RU" type="text/javascript"></script>
        <style>
            body {{ margin: 0; padding: 0; }}
            #map {{ height: 100vh; width: 100%; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            ymaps.ready(function () {{
                var myMap = new ymaps.Map('map', {{
                    center: [0, 0],
                    zoom: 2
                }});
                {markers_js}
            }});
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

