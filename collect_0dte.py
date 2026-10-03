"""
collect_0dte.py
================
Variante di gex_tracker.py pensata per girare ripetutamente durante la
sessione (via GitHub Actions), per catturare snapshot intraday delle
opzioni SPX a scadenza odierna (0DTE) - volume e open interest che si
accumulano nel corso della giornata.

Ogni esecuzione APPENDE una riga con timestamp a 0dte_history.csv,
invece di sovrascrivere. Pensato per essere committato automaticamente
nel repo ad ogni run (vedi .github/workflows/collect_0dte.yml).
"""

import re
import csv
import os
import math
from datetime import datetime, timezone
import requests

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
OUTPUT_CSV = "0dte_history.csv"

OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<date>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")


def fetch_chain():
    headers = {"User-Agent": "Mozilla/5.0 (compatible; 0dte-tracker/1.0)"}
    resp = requests.get(CBOE_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def parse_option_symbol(symbol):
    m = OCC_RE.match(symbol)
    if not m:
        return None
    yy, mm, dd = int(m.group("date")[0:2]), int(m.group("date")[2:4]), int(m.group("date")[4:6])
    expiry_date = datetime(2000 + yy, mm, dd, tzinfo=timezone.utc).date()
    cp = m.group("cp")
    strike = int(m.group("strike")) / 1000.0
    return expiry_date, cp, strike


def collect_0dte_snapshot():
    now = datetime.now(timezone.utc)
    today = now.date()
    chain_json = fetch_chain()
    options = chain_json["data"]["options"]

    total_oi_calls = 0.0
    total_oi_puts = 0.0
    total_volume_calls = 0.0
    total_volume_puts = 0.0
    n_contracts = 0
    atm_iv_values = []

    for opt in options:
        parsed = parse_option_symbol(opt["option"])
        if parsed is None:
            continue
        expiry_date, cp, strike = parsed
        if expiry_date != today:
            continue  # ci interessano solo le 0DTE di OGGI

        oi = opt.get("open_interest") or 0.0
        vol = opt.get("volume") or 0.0
        iv = opt.get("iv") or 0.0

        if cp == "C":
            total_oi_calls += oi
            total_volume_calls += vol
        else:
            total_oi_puts += oi
            total_volume_puts += vol

        if iv > 0:
            atm_iv_values.append(iv)
        n_contracts += 1

    row = {
        "timestamp_utc": now.isoformat(),
        "cboe_data_timestamp": chain_json.get("timestamp"),
        "expiry_date": str(today),
        "total_oi_calls": total_oi_calls,
        "total_oi_puts": total_oi_puts,
        "put_call_oi_ratio": (total_oi_puts / total_oi_calls) if total_oi_calls > 0 else None,
        "total_volume_calls": total_volume_calls,
        "total_volume_puts": total_volume_puts,
        "avg_iv": (sum(atm_iv_values) / len(atm_iv_values)) if atm_iv_values else None,
        "n_contracts_0dte": n_contracts,
    }
    return row


def append_to_csv(row, path=OUTPUT_CSV):
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def main():
    row = collect_0dte_snapshot()
    print("Snapshot 0DTE:")
    for k, v in row.items():
        print(f"  {k}: {v}")
    if row["n_contracts_0dte"] == 0:
        print("\nATTENZIONE: nessun contratto 0DTE trovato (probabile weekend/festivo, "
              "o oggi non e' un giorno con scadenza SPX - verifica il calendario scadenze Cboe aggiornato).")
    append_to_csv(row)
    print(f"\nRiga aggiunta a {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
