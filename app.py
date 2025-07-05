from flask import Flask, request, redirect, render_template
import random
import string

app = Flask(__name__)

# Store links temporarily in memory (will replace with SQLite later)
link_storage = {}

# Helper function to generate a short random slug
def generate_slug(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# 🟢 Route 1: Show the form to input video link + timestamp
@app.route('/', methods=['GET'])
def show_form():
    return render_template('form.html')

# 🟢 Route 2: Handle form submission
@app.route('/create', methods=['POST'])
def create_link():
    original_url = request.form.get('url')
    timestamp = request.form.get('timestamp')

    # 🧠 Append timestamp to URL if provided
    if timestamp:
        if "?" in original_url:
            final_url = f"{original_url}&t={timestamp}"
        else:
            final_url = f"{original_url}?t={timestamp}"
    else:
        final_url = original_url

    # 🔐 Generate a short slug like "a1b2C3"
    slug = generate_slug()

    # 💾 Store the final URL against the slug in memory
    link_storage[slug] = final_url

    return f"Short link created: <a href='/go/{slug}'>/go/{slug}</a>"

# 🟢 Route 3: Redirect when someone clicks the smart link
@app.route('/go/<slug>', methods=['GET'])
def redirect_to_original(slug):
    target_url = link_storage.get(slug)

    if target_url:
        return redirect(target_url)
    else:
        return "Invalid or expired link", 404

# ✅ Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
