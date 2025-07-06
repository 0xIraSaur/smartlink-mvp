from flask import Flask, request, redirect, render_template
import random
import string
import sqlite3
import re
from datetime import datetime

app = Flask(__name__)
DB_FILE = 'links.db'  # SQLite file name

# 🟢 Create the links table if it doesn't exist
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                final_url TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        # Table for click logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT
            )
        ''')

        conn.commit()

# 🔐 Generate a random slug like "a1B2c3"
def generate_slug(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# 🟢 Route 1: Show form
@app.route('/', methods=['GET'])
def show_form():
    return render_template('form.html')

# 🟢 Route 2: Handle form submission and save to DB
@app.route('/create', methods=['POST'])
def create_link():
    original_url = request.form.get('url')
    timestamp = request.form.get('timestamp')

    # Append timestamp if given
    if timestamp:
        if "?" in original_url:
            final_url = f"{original_url}&t={timestamp}"
        else:
            final_url = f"{original_url}?t={timestamp}"
    else:
        final_url = original_url

    slug = generate_slug()
    created_at = datetime.utcnow().isoformat()

    # Save to SQLite
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO links (slug, final_url, created_at) VALUES (?, ?, ?)',
                       (slug, final_url, created_at))
        conn.commit()

    return f"Short link created: <a href='/go/{slug}'>/go/{slug}</a>"

def is_safe_browser(user_agent):
    """
    Determines whether the browser is known to safely support intent:// redirects.
    """
    safe_browsers = ['Chrome', 'Brave', 'Firefox', 'SamsungBrowser']
    return any(browser in user_agent for browser in safe_browsers)



# 🟢 Route 3: Redirect to actual URL
@app.route('/go/<slug>', methods=['GET'])
def redirect_to_original(slug):
    # Connect to SQLite DB
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Look up the final URL using the short slug
        cursor.execute("SELECT final_url FROM links WHERE slug = ?", (slug,))
        result = cursor.fetchone()

        if not result:
            return "Invalid or expired link", 404

        final_url = result[0]

        # Log the click
        timestamp = datetime.utcnow().isoformat()
        ip = request.remote_addr or "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")

        cursor.execute('''
            INSERT INTO clicks (slug, timestamp, ip, user_agent)
            VALUES (?, ?, ?, ?)
        ''', (slug, timestamp, ip, user_agent))

        conn.commit()

        # 🧠 Platform Detection: Basic logic using the user agent string
        platform = "android" if "Android" in user_agent else "ios" if "iPhone" in user_agent or "iPad" in user_agent else "web"
        print(f"Detected platform: {platform}, UA: {user_agent}")

        # 🧪 Special handling for YouTube links with timestamp
        if "youtu" in final_url:
            # Parse video ID and timestamp if exists
            import re
            from urllib.parse import urlparse, parse_qs

            video_id = ""
            start_seconds = 0

            # Case 1: Short link format like youtu.be/<id>?t=3m20s
            if "youtu.be/" in final_url:
                match = re.search(r"youtu\.be/([^?]+)", final_url)
                if match:
                    video_id = match.group(1)
                query = urlparse(final_url).query
                params = parse_qs(query)
                if "t" in params:
                    t_value = params["t"][0]
                    # Convert to seconds (e.g. "3m20s" → 200)
                    mins, secs = 0, 0
                    if "m" in t_value and "s" in t_value:
                        mins = int(t_value.split("m")[0])
                        secs = int(t_value.split("m")[1].replace("s", ""))
                    elif "s" in t_value:
                        secs = int(t_value.replace("s", ""))
                    start_seconds = mins * 60 + secs

            # Case 2: watch?v=<id>&t=200s
            elif "watch?v=" in final_url:
                parsed = urlparse(final_url)
                query = parse_qs(parsed.query)
                video_id = query.get("v", [""])[0]
                if "t" in query:
                    t_value = query["t"][0]
                    if "s" in t_value:
                        start_seconds = int(t_value.replace("s", ""))
                    else:
                        try:
                            start_seconds = int(t_value)
                        except:
                            start_seconds = 0

            # Final fallback if no ID found
            if not video_id:
                return redirect(final_url)

            # 🔁 Platform-specific behavior
            if platform == "android":
                # Intent deep link with fallback
                intent_url = (
                    f"intent://www.youtube.com/watch?v={video_id}&t={start_seconds}s"
                    f"#Intent;scheme=https;"
                    f"package=com.google.android.youtube;"
                    f"S.browser_fallback_url=https://www.youtube.com/watch?v={video_id}&t={start_seconds}s;"
                    f"end"
                )
                print(f"[ANDROID] Redirecting to YouTube via intent: {intent_url}")
                return redirect(intent_url)

            elif platform == "ios":
                # iOS handles https:// links fine
                print("[iOS] Redirecting to YouTube via HTTPS")
                return redirect(f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s")

            else:
                # Default browser (web) fallback
                print("[WEB] Redirecting to YouTube via HTTPS")
                return redirect(f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}s")

        # 🌐 For non-YouTube links, redirect as-is
        return redirect(final_url)
    
            
@app.route('/stats/<slug>', methods=['GET'])
def stats(slug):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Check if the slug exists in the links table
        cursor.execute('SELECT final_url FROM links WHERE slug = ?', (slug,))
        link_result = cursor.fetchone()

        if not link_result:
            return "Link not found", 404

        # Get click logs for this slug
        cursor.execute('''
            SELECT timestamp, ip, user_agent
            FROM clicks
            WHERE slug = ?
            ORDER BY timestamp DESC
            LIMIT 50
        ''', (slug,))
        clicks = cursor.fetchall()

        # Render HTML manually (or we can use templates later)
        response = f"<h2>Stats for: /go/{slug}</h2>"
        response += f"<p><strong>Target URL:</strong> {link_result[0]}</p>"
        response += f"<p><strong>Total Clicks:</strong> {len(clicks)}</p><hr>"

        response += "<h3>Recent Clicks:</h3><ul>"
        for c in clicks:
            ts, ip, ua = c
            response += f"<li>{ts} - IP: {ip} - UA: {ua}</li>"
        response += "</ul>"

        return response

def detect_platform(user_agent: str) -> str:
    ua = user_agent.lower()

    if 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        return 'ios'
    elif 'android' in ua:
        return 'android'
    else:
        return 'desktop'

def extract_youtube_id(url: str) -> str:
    match = re.search(r'v=([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else ''

# ✅ Initialize DB on first run
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
