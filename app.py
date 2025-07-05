from flask import Flask, request, redirect, render_template
import random
import string
import sqlite3
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

# 🟢 Route 3: Redirect to actual URL
@app.route('/go/<slug>', methods=['GET'])
def redirect_to_original(slug):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT final_url FROM links WHERE slug = ?', (slug,))
        result = cursor.fetchone()

        if result:
            target_url = result[0]

            # Extract request data
            timestamp = datetime.utcnow().isoformat()
            ip = request.remote_addr or "unknown"
            user_agent = request.headers.get('User-Agent', 'unknown')

            # Insert into clicks table
            cursor.execute('''
                INSERT INTO clicks (slug, timestamp, ip, user_agent)
                VALUES (?, ?, ?, ?)
            ''', (slug, timestamp, ip, user_agent))

            conn.commit()

            return redirect(target_url)
        else:
            return "Invalid or expired link", 404
        
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


# ✅ Initialize DB on first run
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
