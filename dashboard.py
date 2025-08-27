from flask import Flask, render_template_string
from scrape_marktplaats import fetch_all_listings, SEARCH_URL

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>Listings Dashboard</title>
</head>
<body>
    <h1>Listings Dashboard</h1>
    <table border="1">
        <tr>
            <th>Title</th>
            <th>Price</th>
            <th>Location</th>
            <th>Link</th>
        </tr>
        {% for item in listings %}
        <tr>
            <td>{{ item.title }}</td>
            <td>{{ item.price or 'N/A' }}</td>
            <td>{{ item.location or 'N/A' }}</td>
            <td><a href="{{ item.url }}" target="_blank">View</a></td>
        </tr>
        {% endfor %}
    </table>
    <p>Total products scraped: {{ listings|length }}</p>
</body>
</html>
"""

@app.route("/")
def index():
    listings = fetch_all_listings(SEARCH_URL)
    return render_template_string(TEMPLATE, listings=listings)

if __name__ == "__main__":
    app.run(debug=True)
