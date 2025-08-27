import json
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.marktplaats.nl/q/solis+espresso+apparaat"


def fetch_listings(url: str) -> List[Dict[str, str]]:
    """Return a list of product information dictionaries from a Marktplaats search page."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        raise RuntimeError("Unable to locate data script in page")
    data = json.loads(script.string)
    search = data["props"]["pageProps"]["searchRequestAndResponse"]
    listings = search.get("listings", [])
    products = []
    for item in listings:
        price_info = item.get("priceInfo", {})
        price_cents = price_info.get("priceCents")
        price = f"€{price_cents / 100:.2f}" if price_cents is not None else None
        product = {
            "id": item.get("itemId"),
            "title": item.get("title"),
            "price": price,
            "location": item.get("location", {}).get("locationName"),
            "url": "https://www.marktplaats.nl" + item.get("vipUrl", ""),
        }
        products.append(product)
    return products


def main() -> None:
    products = fetch_listings(SEARCH_URL)
    for p in products:
        print(f"{p['title']} - {p['price']} - {p['url']}")
    print(f"Total products scraped: {len(products)}")


if __name__ == "__main__":
    main()
