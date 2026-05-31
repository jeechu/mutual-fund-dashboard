# Mutual Fund Dashboard

Experimental project to parse eCAS and view Mutual Fund data. Built with Claude.

Uses publicly available APIs for fund and NAV data hosted in [https://mf.captnemo.in](https://mf.captnemo.in)

## Parse eCAS

1. Download eCAS from camsonline
2. Run `python3 parse_cas.py [path/to/CAS.pdf]` to process PDF and generate CSV files.

## Fetch fund and NAV data

1. Run the files `fetch_funds.py` and `get_nav.py`

`get_nav.py` can be run repeatedly to fetch new NAV data.

## View dashboard

Run `python3 -m http.server`
