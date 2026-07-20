import os
import requests

import woko


listing_keys = [
    "title",
    "available_from",
    "available_until",
    "address",
    "name",
    "contact",
    "price",
    "url",
    "other_tennants",
    "viewings",
    "extra",
]


def _load_existing_lines(path):
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.rstrip("\n") for line in f if line.strip()}


def _format_listing_line(listing):
    return " | ".join(
        str(listing.get(k)) for k in
        ("title", "available_from", "address", "price", "url")
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
        f"Address: {listing['address']}\n"
        f"Price: {listing['price']}\n"
        f"Link: {listing['url']}"
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
    notify_discord = False

    _load_dotenv()
    listings = woko.scrape()
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
        if notify_discord:
            _notify_discord(new_listings)

    for i, listing in enumerate(listings, start=1):
        print(f"{i}. {listing['title']}")
        print(f"   Available from: {listing['available_from']}")
        print(f"   Address: {listing['address']}")
        print(f"   Price: {listing['price']}")
        print(f"   Link: {listing['url']}")
        print()


if __name__ == "__main__":
    main()
