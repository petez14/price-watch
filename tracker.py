#!/usr/bin/env python3
"""
Canadian price tracker.

Reads products.json, fetches the current price from each store, and appends a row
to data/history.csv. Also writes data/latest.json for the dashboard and
data/alerts.json when something drops.

Run locally with:  python tracker.py
"""

import csv
import json
import os
import re
import sys
import time
import random
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
HISTORY = DATA / "history.csv"
MANUAL = DATA / "manual-prices.csv"
LATEST = DATA / "latest.json"
ALERTS = DATA / "alerts.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}

FIELDS = ["timestamp", "product_id", "retailer", "price", "in_stock", "url", "method", "status"]


# ---------------------------------------------------------------- utilities

def log(msg):
    print(msg, flush=True)


def clean_price(value):
    """Turn '$1,299.99 CAD' or 1299.99 into a float, or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).replace(",", "")
    match = re.search(r"\d+(?:\.\d{1,2})?", text)
    if not match:
        return None
    price = float(match.group())
    return round(price, 2) if 0 < price < 1_000_000 else None


def get(url, timeout=25):
    time.sleep(random.uniform(1.0, 2.5))  # be a polite guest
    return requests.get(url, headers=HEADERS, timeout=timeout)


# ---------------------------------------------------------------- extractors

def from_jsonld(html):
    """Most Canadian retailers embed schema.org Product data. This is the workhorse."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            blob = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in blob if isinstance(blob, list) else [blob]:
            if not isinstance(node, dict):
                continue
            for candidate in [node] + (node.get("@graph") or []):
                if not isinstance(candidate, dict):
                    continue
                offers = candidate.get("offers")
                if not offers:
                    continue
                for offer in offers if isinstance(offers, list) else [offers]:
                    if not isinstance(offer, dict):
                        continue
                    price = clean_price(offer.get("price") or offer.get("lowPrice"))
                    if price:
                        avail = str(offer.get("availability", "")).lower()
                        return price, ("outofstock" not in avail and "soldout" not in avail)
    return None, None


def from_meta(html):
    """Fallback: Open Graph / product meta tags."""
    soup = BeautifulSoup(html, "html.parser")
    for attrs in [
        {"property": "product:price:amount"},
        {"property": "og:price:amount"},
        {"itemprop": "price"},
        {"name": "twitter:data1"},
    ]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            price = clean_price(tag["content"])
            if price:
                return price, True
    return None, None


def from_bestbuy_ca(url):
    """Best Buy Canada exposes a JSON endpoint their own site calls."""
    sku = re.search(r"/(\d{7,9})(?:[/?#]|$)", url)
    if sku:
        api = f"https://www.bestbuy.ca/api/offers/v1/products/{sku.group(1)}/offers"
        try:
            resp = requests.get(api, headers={**HEADERS, "Accept": "application/json"}, timeout=20)
            if resp.ok:
                offers = resp.json()
                offer = offers[0] if isinstance(offers, list) and offers else offers
                price = clean_price(
                    (offer.get("salePrice") if isinstance(offer, dict) else None)
                    or (offer.get("regularPrice") if isinstance(offer, dict) else None)
                )
                if price:
                    stock = offer.get("onlineAvailability", "") if isinstance(offer, dict) else ""
                    return price, str(stock).lower() != "soldout"
        except (requests.RequestException, ValueError, KeyError, IndexError):
            pass
    # fall through to normal page parsing
    resp = get(url)
    resp.raise_for_status()
    price, stock = from_jsonld(resp.text)
    return (price, stock) if price else from_meta(resp.text)


def from_manual(product_id, retailer):
    """Read the newest hand-entered price for stores that block bots."""
    if not MANUAL.exists():
        return None, None
    best_row = None
    with MANUAL.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("product_id") == product_id and row.get("retailer") == retailer:
                if best_row is None or row.get("date", "") >= best_row.get("date", ""):
                    best_row = row
    if not best_row:
        return None, None
    return clean_price(best_row.get("price")), True


def fetch(product_id, source):
    method = source.get("method", "jsonld")
    url = source["url"]
    retailer = source["retailer"]

    if method == "manual":
        price, stock = from_manual(product_id, retailer)
        return price, stock, "manual entry" if price else "no manual price yet"

    if method == "bestbuy_ca":
        price, stock = from_bestbuy_ca(url)
        return price, stock, "ok" if price else "price not found on page"

    resp = get(url)
    if resp.status_code in (403, 429, 503):
        return None, None, f"blocked by store (HTTP {resp.status_code})"
    resp.raise_for_status()

    price, stock = from_jsonld(resp.text)
    if not price:
        price, stock = from_meta(resp.text)
    return price, stock, "ok" if price else "price not found on page"


# ---------------------------------------------------------------- history io

def read_history():
    if not HISTORY.exists():
        return []
    with HISTORY.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_history(rows):
    DATA.mkdir(exist_ok=True)
    new_file = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def previous_prices(history):
    """Last known good price per (product, retailer)."""
    seen = {}
    for row in history:
        if row.get("price"):
            try:
                seen[(row["product_id"], row["retailer"])] = float(row["price"])
            except ValueError:
                continue
    return seen


# ---------------------------------------------------------------- main

def main():
    config = json.loads((ROOT / "products.json").read_text(encoding="utf-8"))
    history = read_history()
    previous = previous_prices(history)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows, alerts, snapshot = [], [], []

    for product in config["products"]:
        pid, pname = product["id"], product["name"]
        target = product.get("target_price")
        log(f"\n{pname}")

        readings = []
        for source in product["sources"]:
            retailer = source["retailer"]
            try:
                price, stock, status = fetch(pid, source)
            except Exception as exc:  # keep one bad store from killing the run
                price, stock, status = None, None, f"error: {type(exc).__name__}"

            rows.append({
                "timestamp": stamp,
                "product_id": pid,
                "retailer": retailer,
                "price": f"{price:.2f}" if price else "",
                "in_stock": "" if stock is None else ("yes" if stock else "no"),
                "url": source["url"],
                "method": source.get("method", "jsonld"),
                "status": status,
            })

            if price:
                was = previous.get((pid, retailer))
                change = round(price - was, 2) if was else None
                arrow = "" if change is None else (f"  ({change:+.2f})" if change else "  (flat)")
                log(f"  {retailer:<22} ${price:,.2f}{arrow}")
                readings.append({
                    "retailer": retailer, "price": price, "url": source["url"],
                    "in_stock": stock, "change": change,
                })
                if change and change < 0:
                    alerts.append({
                        "kind": "drop", "product": pname, "retailer": retailer,
                        "price": price, "was": was, "change": change, "url": source["url"],
                    })
                if target and price <= target:
                    alerts.append({
                        "kind": "target", "product": pname, "retailer": retailer,
                        "price": price, "target": target, "url": source["url"],
                    })
            else:
                log(f"  {retailer:<22} — {status}")

        if readings:
            best = min(readings, key=lambda r: r["price"])
            spread = max(r["price"] for r in readings) - best["price"]
            log(f"  → best ${best['price']:,.2f} at {best['retailer']} "
                f"(spread ${spread:,.2f} across {len(readings)} stores)")
            snapshot.append({
                "id": pid, "name": pname, "target_price": target,
                "updated": stamp, "readings": readings,
            })

    append_history(rows)
    LATEST.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    ALERTS.write_text(json.dumps(alerts, indent=2), encoding="utf-8")

    # Feed the GitHub Actions run summary so you can eyeball a run from your phone
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Price check — {stamp}\n\n")
            for product in snapshot:
                fh.write(f"### {product['name']}\n\n| Store | Price | Change |\n|---|---|---|\n")
                for r in sorted(product["readings"], key=lambda x: x["price"]):
                    delta = f"{r['change']:+.2f}" if r["change"] else "—"
                    fh.write(f"| {r['retailer']} | ${r['price']:,.2f} | {delta} |\n")
                fh.write("\n")

    log(f"\nLogged {len(rows)} readings. {len(alerts)} alert(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
