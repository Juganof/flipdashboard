from flask import Flask, render_template
from scrape_marktplaats import fetch_all_listings, SEARCH_URL

app = Flask(__name__)

@app.route("/")
def index():
    listings = fetch_all_listings(SEARCH_URL)
    return render_template("dashboard.html", listings=listings)

if __name__ == "__main__":
    app.run(debug=True)
