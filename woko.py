from bs4 import BeautifulSoup
import requests

from urllib.parse import urljoin
from listing import listing_keys


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


def _extract_detail_pairs(soup):
    """Pair up croom__title-val-title labels with the following croom__title-val-value."""
    container = soup.select_one("div.croom__title-val")
    if not container:
        return {}
    divs = container.find_all("div", recursive=False)
    pairs = {}
    for key_div, value_div in zip(divs[0::2], divs[1::2]):
        pairs[key_div.get_text(strip=True)] = value_div.get_text(strip=True)
    return pairs


def scrape_detail(detail_url):
    try:
        response = requests.get(detail_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to fetch detail page {detail_url}: {exc}")
        return {}
    soup = BeautifulSoup(response.text, "html.parser")
    return _extract_detail_pairs(soup)


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

    known_text_keys = {"Wann", "Adresse", "Ort"}
    known_detail_keys = {
        "Wann", "Bis", "Adresse", "Kontakt", "Telefon", "E-Mail",
        "Besichtigungstermin", "Anzahl Mitbewohner",
    }

    listings = []
    for el in visible_elements:
        headline = el.select_one("h3.crooms__headline")
        price = el.select_one("span.crooms__price--value")
        link = el.select_one("a.crooms__link--detail")
        texts = _extract_text_pairs(el)

        price_text = price.get_text(strip=True) if price else None
        price_value = _parse_price(price_text)
        if price_value is None:
            continue

        detail_url = urljoin(BASE_URL, link["href"]) if link else None
        details = scrape_detail(detail_url) if detail_url else {}

        street = texts.get("Adresse") or details.get("Adresse")
        city = texts.get("Ort")
        address = f"{street}, {city}" if street and city and city not in street else street

        name = details.get("Kontakt")
        phone = details.get("Telefon")
        email = details.get("E-Mail")
        contact = " / ".join(p for p in (phone, email) if p) or None

        extra = {k: v for k, v in texts.items() if k not in known_text_keys}
        extra.update({k: v for k, v in details.items() if k not in known_detail_keys})
        extra = extra or None

        listing = {key: None for key in listing_keys}
        listing.update({
            "title": headline.get_text(strip=True) if headline else None,
            "available_from": texts.get("Wann") or details.get("Wann"),
            "available_until": details.get("Bis"),
            "address": address,
            "name": name,
            "contact": contact,
            "price": price_value,
            "url": detail_url,
            "other_tennants": details.get("Anzahl Mitbewohner"),
            "viewings": details.get("Besichtigungstermin"),
            "extra": extra,
        })

        listings.append(listing)
    return listings


def main():
    listings = scrape()
    print(f"Found {len(listings)} listing(s):\n")
    for i, listing in enumerate(listings, start=1):
        print(f"{i}. {listing}")


if __name__ == "__main__":
    main()