import json
import os
from pathlib import Path

from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    data_file = Path("marktplaats_listings.json")
    if data_file.exists():
        listings = json.loads(data_file.read_text())
    else:
        listings = None
    return render_template("dashboard.html", listings=listings)

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
