#!/usr/bin/env python3
"""Fetch fund details from mf.captnemo.in/kuvera/<ISIN> for every ISIN found in
transactions.csv and save each response as funds/<ISIN>.json.

Usage:
    python3 fetch_funds.py             # only fetch ISINs that don't have a file yet
    python3 fetch_funds.py --refresh   # re-fetch everything

The API redirects to api.kuvera.in and returns a JSON array with a single fund
object. We unwrap the array and persist the inner object for convenience.
"""
import csv
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

HERE = Path(__file__).parent
TX_CSV = HERE / 'transactions.csv'
OUT_DIR = HERE / 'funds'
API = 'https://mf.captnemo.in/kuvera/{isin}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; PnLTracker/1.0)',
    'Accept': 'application/json',
}


def fetch(isin):
    req = urllib.request.Request(API.format(isin=isin), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    # API returns a 1-element array; unwrap when possible.
    if isinstance(data, list) and len(data) == 1:
        return data[0]
    return data


def unique_isins():
    isins = []
    seen = set()
    with TX_CSV.open() as f:
        for row in csv.DictReader(f):
            isin = (row.get('isin') or '').strip()
            if isin and isin not in seen:
                seen.add(isin)
                isins.append(isin)
    return isins


def main():
    refresh = '--refresh' in sys.argv
    OUT_DIR.mkdir(exist_ok=True)
    isins = unique_isins()
    print(f'{len(isins)} unique ISINs in {TX_CSV.name}')

    fetched = skipped = failed = 0
    for isin in isins:
        path = OUT_DIR / f'{isin}.json'
        if path.exists() and not refresh:
            skipped += 1
            continue
        try:
            data = fetch(isin)
            path.write_text(json.dumps(data, indent=2))
            name = data.get('name') or data.get('short_name') or '(no name)'
            print(f'  ok  {isin}  {name}')
            fetched += 1
            time.sleep(0.4)  # be polite
        except urllib.error.HTTPError as e:
            print(f'  ERR {isin}  HTTP {e.code}', file=sys.stderr)
            failed += 1
        except Exception as e:
            print(f'  ERR {isin}  {e}', file=sys.stderr)
            failed += 1

    print(f'\nDone. fetched={fetched} skipped={skipped} failed={failed}')
    print(f'Files in {OUT_DIR}/')


if __name__ == '__main__':
    main()
