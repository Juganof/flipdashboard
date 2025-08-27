import json
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.marktplaats.nl/q/solis+espresso+apparaat"


def is_commercial(listing: Dict[str, Any]) -> bool:
    """Return True if the listing is a commercial advertisement."""
    seller = listing.get("sellerInformation", {})
    if seller.get("showWebsiteUrl") or seller.get("sellerWebsiteUrl"):
        return True
    if listing.get("admarktInfo"):
        return True
    return False


def fetch_listings(url: str) -> List[Dict[str, str]]:
    """Return non-commercial product information dictionaries from a Marktplaats search page."""
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
        if is_commercial(item):
            continue
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


def fetch_all_listings(url: str) -> List[Dict[str, str]]:
    """Fetch listings from all result pages for a search query."""
    page = 1
    all_products: List[Dict[str, str]] = []
    seen_ids = set()
    while True:
        page_url = f"{url}?p={page}" if page > 1 else url
        products = fetch_listings(page_url)
        new_products = [p for p in products if p["id"] not in seen_ids]
        if not new_products:
            break
        all_products.extend(new_products)
        seen_ids.update(p["id"] for p in new_products)
        page += 1
    return all_products


def main() -> None:
    products = fetch_all_listings(SEARCH_URL)
    for p in products:
        print(f"{p['title']} - {p['price']} - {p['url']}")
    print(f"Total products scraped: {len(products)}")


if __name__ == "__main__":
    main()
