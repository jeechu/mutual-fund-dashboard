#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests


# Configure this URL template.
# The ISIN will be appended to the end of the URL.
# Example:
#     URL_TEMPLATE = "https://api.example.com/security/"
URL_TEMPLATE = "https://mf.captnemo.in/nav/"


# Add your ISINs here
ISINS = [
    'INF579M01902',
    'INF846K01CR6',
    'INF846K01K01',
    'INF846K01B51',
    'INF846K01859',
    'INF0QA701BW3',
    'INF740K01FK9',
    'INF740KA1MB0',
    'INF740K01797',
    'INF740K01PI2',
    'INF740KA1CR7',
    'INF090I01JR0',
    'INF109K016L0',
    'INF109K01Z48',
    'INF109K01Q49',
    'INF174V01010',
    'INF769K01IK2',
    'INF204K01YH3',
    'INF663L01FF1',
    'INF663L01DV3',
    'INF879O01027',
    'INF879O01019',
    'INF879O01365',
    'INF966L01689',
    'INF966L01614',
    'INF966L01648',
    'INF966L01721',
    'INF200K01RA0',
    'INF277K013S8'
]


OUTPUT_DIR = Path("./nav")
TIMEOUT_SECONDS = 30


def fetch_and_save(isin: str) -> None:
    url = URL_TEMPLATE + quote(isin)
    response = requests.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    output_path = OUTPUT_DIR / f"{isin}.json"
    output_path.write_text(response.text, encoding="utf-8")
    print(f"Saved {isin} -> {output_path}")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for isin in ISINS:
        try:
            fetch_and_save(isin)
        except Exception as e:
            print(f"Failed for {isin}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
