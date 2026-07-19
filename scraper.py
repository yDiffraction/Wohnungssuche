"""Scraper for woko.ch's list of free rooms ("Zimmer").

Simulates picking <option value="0"> ("Zimmer") from the
<select class="crooms__form-select" name="so_typ"> filter, then lists the
listings that would become visible under that filter.

The site filters listings entirely client-side (JS toggles a "js-hidden"
class on each <div class="crooms__element"> based on its data-typ attribute),
so this replicates that by keeping only elements whose data-typ matches the
selected option's value.
"""

import os

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://www.woko.ch/unser-angebot/freie-objekte"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _extract_text_pairs(element):
    """Pair up crooms__text--key labels with the following crooms__text value."""
    text_col = element.select_one("div.crooms__column--text")
    if not text_col:
        return {}
    divs = text_col.find_all("div", recursive=False)
    pairs = {}
    for key_div, value_div in zip(divs[0::2], divs[1::2]):
        pairs[key_div.get_text(strip=True)] = value_div.get_text(strip=True)
    return pairs


def _parse_price(text):
    """Parse a Swiss-formatted price like "1'180.-" or "1'180.50" (rappen) into an int."""
    if not text:
        return None
    cleaned = text.replace("’", "").replace("'", "").strip()
    if cleaned.endswith(".-"):
        cleaned = cleaned[:-2]
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def scrape():
    response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    typ_select = soup.select_one('select.crooms__form-select[name="so_typ"]')
    target_option = typ_select.select_one('option[value="0"]')
    target_value = target_option["value"]

    elements_container = soup.select_one("div.crooms__elements")
    all_elements = elements_container.find_all("div", class_="crooms__element", recursive=False)
    visible_elements = [el for el in all_elements if el.get("data-typ") == target_value]

    listings = []
    for el in visible_elements:
        headline = el.select_one("h3.crooms__headline")
        price = el.select_one("span.crooms__price--value")
        link = el.select_one("a.crooms__link--detail")
        texts = _extract_text_pairs(el)

        price_text = price.get_text(strip=True) if price else None
        price_value = _parse_price(price_text)
        if price_value is None or price_value >= 900:
            continue

        listings.append(
            {
                "title": headline.get_text(strip=True) if headline else None,
                "available_from": texts.get("Wann"),
                "address": texts.get("Adresse"),
                "city": texts.get("Ort"),
                "price": price_text,
                "detail_url": urljoin(BASE_URL, link["href"]) if link else None,
            }
        )
    return listings


def _load_existing_lines(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.rstrip("\n") for line in f if line.strip()}


def _format_listing_line(listing):
    return " | ".join(
        str(listing.get(k)) for k in
        ("title", "available_from", "address", "city", "price", "detail_url")
    )


def _load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _format_listing_block(listing):
    return (
        f"**{listing['title']}**\n"
        f"Available from: {listing['available_from']}\n"
        f"Address: {listing['address']}, {listing['city']}\n"
        f"Price: {listing['price']}\n"
        f"Link: {listing['detail_url']}"
    )


def _chunk_messages(blocks, limit=2000):
    chunks = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > limit and current:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _notify_discord(listings):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set; skipping Discord notification.")
        return

    blocks = [_format_listing_block(listing) for listing in listings]
    for chunk in _chunk_messages(blocks):
        response = requests.post(webhook_url, json={"content": chunk}, timeout=15)
        response.raise_for_status()


def main():
    _load_dotenv()
    listings = scrape()
    print(f"Found {len(listings)} listing(s):\n")

    listings_file = "listings.txt"
    existing_lines = _load_existing_lines(listings_file)
    new_listings = [
        listing for listing in listings
        if _format_listing_line(listing) not in existing_lines
    ]
    if new_listings:
        with open(listings_file, "a", encoding="utf-8") as f:
            for listing in new_listings:
                f.write(_format_listing_line(listing) + "\n")
        _notify_discord(new_listings)

    for i, listing in enumerate(listings, start=1):
        print(f"{i}. {listing['title']}")
        print(f"   Available from: {listing['available_from']}")
        print(f"   Address: {listing['address']}, {listing['city']}")
        print(f"   Price: {listing['price']}")
        print(f"   Link: {listing['detail_url']}")
        print()


if __name__ == "__main__":
    main()
