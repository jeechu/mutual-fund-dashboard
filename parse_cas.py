#!/usr/bin/env python3
"""Parse a CAMS/KFintech CAS PDF into transactions.csv and transaction_summary.csv.

Usage:
    python3 parse_cas.py [path/to/CAS.pdf]

If no PDF path is given, the script picks the first *.pdf in its own directory.
Outputs are written next to the PDF as:
    - transactions.csv         (one row per financial transaction)
    - transaction_summary.csv  (one row per (folio, ISIN) fund holding)

Stamp duty, STT, address/nominee updates, registration changes, SIP register/pause
and cancelled entries are intentionally excluded.

Dependencies: pdfplumber (pip install pdfplumber)
"""
import re
import csv
import sys
from pathlib import Path
from collections import defaultdict


# ---------- Regexes ----------
FOLIO_RE = re.compile(r'^Folio No:\s*([0-9A-Z]+)\s*(?:/\s*\d+)?\s+PAN:', re.I)
# Scheme line — allow text between ISIN and (Advisor:...) for wrapped lines
SCHEME_RE = re.compile(
    r'^([A-Z0-9]+)-(.+?)\s*-\s*ISIN:\s*([A-Z0-9]+)[^()]*?\(Advisor:\s*([^)]+)\)',
    re.I,
)
REGISTRAR_RE = re.compile(r'Registrar\s*:\s*(\S+)', re.I)
DATE_RE = re.compile(r'^(\d{2}-[A-Za-z]{3}-\d{4})\s+(.*)$')
NUM = r'\(?-?[\d,]+\.\d+\)?'
TXN_TAIL_RE = re.compile(
    r'(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s*$'
)

# Skip these (non-financial / fee entries)
SKIP_PATTERNS = [
    r'\*\*\*\s*Stamp Duty',
    r'\*\*\*\s*STT Paid',
    r'\*\*\*Address',
    r'\*\*\*Registration',
    r'\*\*\*Change',
    r'\*\*\*Cancelled',
    r'\*\*\*Updation',
    r'\*\*\*SIP Registered',
    r'\*\*\*SIP Pause',
    r'\*\*\*SIPSystematic',
    r'\*\*\*Consolidation',
    r'\*\*\*\*\*\*Address',
    r'\*\*\*\*\*Address',
]
SKIP_RE = re.compile('|'.join(SKIP_PATTERNS), re.I)


def num(s):
    s = s.replace(',', '').strip()
    if s.startswith('(') and s.endswith(')'):
        return -float(s[1:-1])
    return float(s)


def classify(desc):
    d = desc.lower()
    if 'redemption' in d:
        return 'Redemption'
    if 'switch out' in d or 'switch-out' in d or 'switchout' in d:
        return 'Switch Out'
    if 'switch in' in d or 'switch-in' in d:
        return 'Switch In'
    if 'reversal' in d:
        return 'Reversal'
    if ('sip purchase' in d or 'systematic investment' in d
            or 'systematic-bse' in d or 'purchase systematic' in d
            or 'sip purchase-bse' in d):
        return 'SIP Purchase'
    if 'nfo purchase' in d:
        return 'NFO Purchase'
    if 'initial purchase' in d:
        return 'Initial Purchase'
    if 'new purchase' in d:
        return 'New Purchase'
    if 'additional purchase' in d:
        return 'Additional Purchase'
    if 'purchase' in d:
        return 'Purchase'
    return 'Other'


def extract_text(pdf_path):
    import pdfplumber
    text = ''
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text(x_tolerance=2, y_tolerance=2) or ''
            text += f'\n===PAGE {i+1}===\n' + t
    return text


def parse(raw_text):
    lines = raw_text.splitlines()
    transactions = []
    current = {k: None for k in
               ('folio', 'fund_name', 'isin', 'advisor', 'registrar', 'amc')}
    amc = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # AMC header (e.g. "PPFAS Mutual Fund", "Quant MF", "360 ONE Mutual Fund")
        if re.match(r'^[A-Z0-9][A-Za-z0-9 &.]+(Mutual Fund|MF|MUTUAL FUND)\s*$', line):
            amc = line
            i += 1
            continue

        fm = FOLIO_RE.match(line)
        if fm:
            current['folio'] = fm.group(1)
            current['amc'] = amc
            current['fund_name'] = None
            current['isin'] = None
            current['advisor'] = None
            current['registrar'] = None
            i += 1
            continue

        # Scheme line, possibly wrapped over 2 lines
        sm = SCHEME_RE.match(line)
        joined = line
        if not sm and i + 1 < len(lines):
            joined = line + ' ' + lines[i + 1].strip()
            sm = SCHEME_RE.match(joined)
        if sm:
            current['fund_name'] = sm.group(2).strip()
            current['isin'] = sm.group(3).strip()
            current['advisor'] = sm.group(4).strip()

            # registrar — same line, then look ahead, then bare "KFINTECH"/"CAMS"
            current['registrar'] = None
            for k in range(0, 4):
                if i + k < len(lines):
                    rm = REGISTRAR_RE.search(lines[i + k])
                    if rm:
                        current['registrar'] = rm.group(1).strip()
                        break
            if not current['registrar'] or current['registrar'] == ':':
                for k in range(1, 5):
                    if i + k < len(lines):
                        s = lines[i + k].strip()
                        if s in ('KFINTECH', 'CAMS'):
                            current['registrar'] = s
                            break
            i += 1
            continue

        # Transaction line?
        dm = DATE_RE.match(line)
        if dm and current['folio'] and current['fund_name']:
            date = dm.group(1)
            rest = dm.group(2).strip()
            if SKIP_RE.search(rest):
                i += 1
                continue
            tm = TXN_TAIL_RE.search(rest)
            if tm:
                try:
                    amount = num(tm.group(1))
                    units = num(tm.group(2))
                    price = num(tm.group(3))
                except ValueError:
                    i += 1
                    continue
                desc = rest[:tm.start()].strip()
                transactions.append({
                    'date': date,
                    'folio': current['folio'],
                    'amc': current['amc'],
                    'fund_name': current['fund_name'],
                    'isin': current['isin'],
                    'advisor': current['advisor'],
                    'registrar': current['registrar'],
                    'transaction_type': classify(desc),
                    'description': desc,
                    'amount': amount,
                    'units': units,
                    'price': price,
                })
        i += 1
    return transactions


def write_outputs(transactions, out_dir):
    out_dir = Path(out_dir)

    tx_path = out_dir / 'transactions.csv'
    fields = ['date', 'folio', 'amc', 'fund_name', 'isin', 'advisor', 'registrar',
              'transaction_type', 'description', 'amount', 'units', 'price']
    with tx_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for t in transactions:
            w.writerow(t)

    # Summary by (folio, isin) — uses FIFO within folio for current_units & cost basis.
    # Redemption / switch-out consumes oldest purchase lots first (same folio only).
    from datetime import datetime
    def parse_date(s):
        return datetime.strptime(s, '%d-%b-%Y')

    # group txns by (folio, isin) in chronological order
    by_key = defaultdict(list)
    for t in transactions:
        by_key[(t['folio'], t['isin'])].append(t)
    for k in by_key:
        by_key[k].sort(key=lambda x: parse_date(x['date']))

    agg = {}
    for key, txns in by_key.items():
        folio, isin = key
        lots = []   # FIFO queue: [{units, price}]
        purchase_amount = 0.0
        purchase_units = 0.0
        redemption_amount = 0.0
        redemption_units = 0.0
        for t in txns:
            if t['units'] >= 0:  # buy (purchase / SIP / switch in)
                purchase_amount += t['amount']
                purchase_units += t['units']
                if t['units'] > 0:
                    lots.append({'units': t['units'], 'price': t['price']})
            else:  # sell (redemption / switch out / reversal)
                redemption_amount += t['amount']
                redemption_units += t['units']
                remaining = -t['units']  # units to remove (positive)
                while remaining > 1e-6 and lots:
                    lot = lots[0]
                    if lot['units'] <= remaining + 1e-6:
                        remaining -= lot['units']
                        lots.pop(0)
                    else:
                        lot['units'] -= remaining
                        remaining = 0
        current_units = sum(l['units'] for l in lots)
        current_invested = sum(l['units'] * l['price'] for l in lots)
        agg[key] = {
            'folio': folio,
            'amc': txns[0]['amc'],
            'fund_name': txns[0]['fund_name'],
            'isin': isin,
            'advisor': txns[0]['advisor'],
            'registrar': txns[0]['registrar'],
            'txn_count': len(txns),
            'total_invested': round(purchase_amount, 2),
            'total_redeemed': round(abs(redemption_amount), 2),
            'purchase_units': round(purchase_units, 4),
            'redemption_units': round(abs(redemption_units), 4),
            'current_units': round(max(current_units, 0), 4),
            'current_invested': round(max(current_invested, 0), 2),
        }

    sum_path = out_dir / 'transaction_summary.csv'
    sum_fields = ['folio', 'amc', 'fund_name', 'isin', 'advisor', 'registrar',
                  'txn_count', 'total_invested', 'total_redeemed',
                  'purchase_units', 'redemption_units',
                  'current_units', 'current_invested']
    with sum_path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=sum_fields)
        w.writeheader()
        for _, row in sorted(agg.items(),
                             key=lambda x: (x[1]['amc'] or '', x[1]['fund_name'])):
            w.writerow(row)

    return tx_path, sum_path, len(agg)


def main():
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1])
    else:
        here = Path(__file__).parent
        pdfs = sorted(here.glob('*.pdf'))
        if not pdfs:
            sys.exit('No PDF given and none found in script directory.')
        pdf_path = pdfs[0]
        print(f'Using PDF: {pdf_path.name}')

    raw = extract_text(pdf_path)
    txns = parse(raw)
    tx_path, sum_path, n_funds = write_outputs(txns, pdf_path.parent)

    total_p = sum(t['amount'] for t in txns if t['amount'] >= 0)
    total_r = sum(t['amount'] for t in txns if t['amount'] < 0)
    import csv as _csv
    with open(sum_path) as f:
        rows = list(_csv.DictReader(f))
    current_invested = sum(float(r['current_invested']) for r in rows)
    print(f'Wrote {len(txns)} transactions  -> {tx_path}')
    print(f'Wrote {n_funds} fund holdings    -> {sum_path}')
    print(f'Total invested:     {total_p:>15,.2f}')
    print(f'Total redeemed:     {-total_r:>15,.2f}')
    print(f'Current invested:   {current_invested:>15,.2f}  (FIFO cost basis of currently-held units)')


if __name__ == '__main__':
    main()
