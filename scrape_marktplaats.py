"""Utilities for scraping Marktplaats search results.

This module fetches listing information from Marktplaats search pages.  The
original implementation only returned a small subset of details available in
the result payload.  The scraper has been extended to parse additional fields
such as the listing description, seller information and shipping options.  If a
field is not available in the search results payload we fetch the individual
listing page and parse its ``__NEXT_DATA__`` object to obtain the remaining
data.
"""

import json
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.marktplaats.nl/q/solis+espresso+apparaat"
DB_PATH = "data.db"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "TE": "trailers",
}



def _init_db(conn: sqlite3.Connection) -> None:
    """Create the listings table if it does not yet exist."""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            title TEXT,
            price REAL,
            status TEXT,
            last_seen TEXT,
            final_price REAL,
            url TEXT
        )
        """
    )
    conn.commit()


def _update_database(products: List[Dict[str, Any]]) -> None:
    """Insert new listings or update existing records in the SQLite database."""

    conn = sqlite3.connect(DB_PATH)
    _init_db(conn)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()

    seen_ids = set()
    for product in products:
        seen_ids.add(str(product["id"]))
        price = None
        if product.get("price"):
            try:
                price = float(product["price"].replace("€", ""))
            except ValueError:
                price = None
        cur.execute(
            """
            INSERT INTO listings (id, title, price, status, last_seen, url)
            VALUES (?, ?, ?, 'available', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                price=excluded.price,
                status='available',
                last_seen=excluded.last_seen,
                url=excluded.url
            """,
            (
                product.get("id"),
                product.get("title"),
                price,
                now,
                product.get("url"),
            ),
        )

    # Mark listings not seen in this scrape as sold
    cur.execute("SELECT id FROM listings WHERE status='available'")
    existing_ids = {row[0] for row in cur.fetchall()}
    missing = existing_ids - seen_ids
    for listing_id in missing:
        cur.execute(
            "UPDATE listings SET status='sold', final_price=price, price=NULL WHERE id=?",
            (listing_id,),
        )

    conn.commit()
    conn.close()

def init_db(path: str = "listings.db") -> sqlite3.Connection:
    """Create the listings table if needed and return a connection."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY, data TEXT, status TEXT)"
    )
    return conn


def save_listings(conn: sqlite3.Connection, listings: List[Dict[str, Any]]) -> None:
    """Insert listings into the database with a default ``new`` status."""
    for listing in listings:
        conn.execute(
            "INSERT OR IGNORE INTO listings (id, data, status) VALUES (?, ?, 'new')",
            (listing["id"], json.dumps(listing)),
        )
    conn.commit()


def get_new_listings(conn: sqlite3.Connection) -> tuple[List[Dict[str, Any]], List[str]]:
    """Return listings marked as ``new`` along with their ids."""
    cur = conn.execute("SELECT id, data FROM listings WHERE status='new'")
    rows = cur.fetchall()
    listings = [json.loads(row[1]) for row in rows]
    ids = [row[0] for row in rows]
    return listings, ids


def mark_listings_active(conn: sqlite3.Connection, ids: List[str]) -> None:
    """Mark listings with the provided ids as ``active``."""
    conn.executemany("UPDATE listings SET status='active' WHERE id=?", [(i,) for i in ids])
    conn.commit()


def notify_new_listing(listing: Dict[str, Any]) -> None:
    """Send an alert for a newly discovered listing."""
    print(f"New listing: {listing.get('title')} -> {listing.get('url')}")


def is_commercial(listing: Dict[str, Any]) -> bool:
    """Return True if the listing is a commercial advertisement."""
    seller = listing.get("sellerInformation", {})
    if seller.get("showWebsiteUrl") or seller.get("sellerWebsiteUrl"):
        return True
    if listing.get("admarktInfo"):
        return True
    return False


def is_broken_product(listing: Dict[str, Any]) -> bool:
    """Return ``True`` if a listing advertises a damaged item.

    The check looks for common keywords that sellers use when offering
    products that are defective or only suitable for spare parts.  Both the
    description text and any attribute values are inspected.
    """

    keywords = ["defect", "broken", "parts", "spares", "repair"]

    # Collect text fields to scan for the keywords.
    text_parts: List[str] = []
    description = listing.get("description") or ""
    text_parts.append(description.lower())

    attributes = listing.get("attributes") or []
    for attr in attributes:
        for value in attr.values():
            if isinstance(value, str):
                text_parts.append(value.lower())

    text = " ".join(text_parts)
    return any(keyword in text for keyword in keywords)


def _parse_listing_script(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract the JSON payload from the ``__NEXT_DATA__`` script element."""

    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        raise RuntimeError("Unable to locate data script in page")
    return json.loads(script.string)


def fetch_listing_details(vip_url: str) -> Dict[str, Any]:
    """Fetch additional information for a listing.

    Parameters
    ----------
    vip_url:
        Absolute URL of the listing's detail page.

    Returns
    -------
    dict
        Dictionary containing extra fields such as description, seller details
        and shipping options.  Returns an empty dictionary when the payload
        cannot be located.
    """

    response = requests.get(vip_url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    try:
        data = _parse_listing_script(soup)
    except RuntimeError:
        return {}

    listing = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("listing", {})
    )

    seller = listing.get("sellerInformation") or {}
    return {
        "description": listing.get("description"),
        "seller_name": seller.get("sellerName"),
        "seller_rating": seller.get("sellerReviewAverage")
        or seller.get("sellerReviewScore"),
        "start_date": listing.get("startDate") or listing.get("date"),
        "shipping_options": listing.get("shippingOptions"),
        "attributes": listing.get("attributes"),
    }


def fetch_listings(url: str) -> List[Dict[str, Any]]:
    """Return non-commercial product dictionaries from a search results page.

    Each product dictionary now contains additional information such as the
    description, seller details, posting date, shipping options and attribute
    list.  When certain fields are missing from the search results payload we
    fall back to fetching the listing's detail page.
    """

    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    data = _parse_listing_script(soup)
    search = data["props"]["pageProps"]["searchRequestAndResponse"]
    listings = search.get("listings", [])
    products: List[Dict[str, Any]] = []

    for item in listings:
        if is_commercial(item):
            continue

        price_info = item.get("priceInfo", {})
        price_cents = price_info.get("priceCents")
        price = f"€{price_cents / 100:.2f}" if price_cents is not None else None

        image_urls = item.get("imageUrls") or []
        image_url: Optional[str] = None
        if image_urls:
            first = image_urls[0]
            image_url = "https:" + first if first.startswith("//") else first

        seller = item.get("sellerInformation") or {}

        product: Dict[str, Any] = {
            "id": item.get("itemId"),
            "title": item.get("title"),
            "price": price,
            "location": item.get("location", {}).get("locationName"),
            "url": "https://www.marktplaats.nl" + item.get("vipUrl", ""),
            "image_url": image_url,
            "description": item.get("description"),
            "seller": seller,
            "seller_rating": seller.get("sellerReviewAverage")
            or seller.get("sellerReviewScore"),
            "start_date": item.get("startDate") or item.get("date"),
            "shipping_options": item.get("shippingOptions"),
            "attributes": item.get("attributes"),
        }

        # Fill in any missing fields from the listing detail page.
        details = fetch_listing_details(product["url"])
        for key, value in details.items():
            if product.get(key) in (None, [], {}):
                product[key] = value

        product["is_broken"] = is_broken_product(product)
        if not product["is_broken"]:
            continue

        products.append(product)

    return products


def fetch_all_listings(url: str) -> List[Dict[str, Any]]:
    """Fetch listings from all result pages for a search query."""

    page = 1
    all_products: List[Dict[str, Any]] = []
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
        time.sleep(2) # Add a 2-second delay between page requests

    return all_products


def main() -> None:

    products = fetch_all_listings(SEARCH_URL)
    _update_database(products)
    with open("marktplaats_listings.json", "w") as f:
        json.dump(products, f, indent=4)
    print(f"Total products scraped: {len(products)}")

    conn = init_db()
    try:
        products = fetch_all_listings(SEARCH_URL)
        save_listings(conn, products)

        new_listings, ids = get_new_listings(conn)
        for listing in new_listings:
            notify_new_listing(listing)
        if ids:
            mark_listings_active(conn, ids)

        with open("marktplaats_listings.json", "w") as f:
            json.dump(products, f, indent=4)
        print(f"Total products scraped: {len(products)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
