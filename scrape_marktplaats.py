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
from typing import Any, Dict, List, Optional

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

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(vip_url, headers=headers, timeout=30)
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

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=30)
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
            "seller_name": seller.get("sellerName"),
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

    return all_products


def main() -> None:
    products = fetch_all_listings(SEARCH_URL)
    for p in products:
        print(f"{p['title']} - {p['price']} - {p['url']}")
    print(f"Total products scraped: {len(products)}")


if __name__ == "__main__":
    main()
