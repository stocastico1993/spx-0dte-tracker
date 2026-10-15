"""
collect_0dte.py  (v3)
=====================
Raccoglie uno snapshot della catena opzioni SPX/SPXW con scadenza OGGI (0DTE)
dal feed gratuito CBOE e lo salva in due posti:

  data/summary_0dte.csv           una riga per snapshot: totali, ATM IV, GEX
  data/strikes_YYYY-MM-DD.csv     una riga per contratto per snapshot
                                  (solo strike entro +/- BAND_PCT dallo spot)

Novita' della v3 (colonne aggiunte IN FONDO al summary, quelle vecchie invariate):
  * n_contracts_all, gex_all_calls, gex_all_puts, net_gex_all, gex_all_norm:
    stesso GEX ma su TUTTE le scadenze della catena (la letteratura usa questa)
  * quality: "ok" oppure i motivi per cui lo snapshot non e' affidabile:
    apertura (prima delle 10:00 NY), spot (parity e campo CBOE distanti > 0,1%),
    spot_mancante, gex_zero
  * al primo avvio il summary esistente riceve le colonne nuove (vuote per le righe vecchie)

Differenze della v2 rispetto alla v1:
  * salva i dati per strike (la v1 teneva solo i totali)
  * l'orario di mercato e' controllato DENTRO lo script, in fuso America/New_York:
    il cambio dell'ora legale non richiede piu' nessuna modifica
  * se l'ultimo snapshot e' piu' recente di MIN_GAP_SECONDS non scrive niente,
    cosi' due trigger ravvicinati (GitHub + cron-job.org) non creano doppioni
  * se non ci sono contratti 0DTE (weekend, festivi) non scrive righe vuote
  * nessuna dipendenza esterna (solo libreria standard)

Uso:
    python collect_0dte.py            # uso normale
    python collect_0dte.py --force    # ignora filtro orario e deduplica (solo test)
"""

import csv
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone, time as dtime
from zoneinfo import ZoneInfo

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
ET = ZoneInfo("America/New_York")

MARKET_OPEN = dtime(9, 30)    # ora di New York
MARKET_CLOSE = dtime(16, 15)  # ora di New York
MIN_GAP_SECONDS = 9 * 60      # sotto questa distanza dall'ultimo snapshot: salta
BAND_PCT = 0.07               # strike salvati: spot +/- 7%
MULTIPLIER = 100
OPENING_UNRELIABLE_UNTIL = dtime(10, 0)  # prima di quest'ora (NY) lo snapshot e' segnato "apertura"
SPOT_MISMATCH_PCT = 0.001     # spot parity vs campo CBOE: oltre lo 0,1% lo snapshot e' segnato "spot"

DATA_DIR = "data"
SUMMARY_NAME = "summary_0dte.csv"

OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<date>\d{6})(?P<cp>[CP])(?P<strike>\d{8})$")

SUMMARY_FIELDS = [
    "snapshot_utc", "snapshot_et", "cboe_timestamp", "expiry", "spot_parity",
    "spot_cboe_field", "n_contracts", "oi_calls", "oi_puts", "pc_oi_ratio",
    "vol_calls", "vol_puts", "pc_vol_ratio", "iv_atm",
    "gex_calls", "gex_puts", "net_gex", "gex_norm",
    # v3: gamma su TUTTE le scadenze (stessa formula, stesso segno call +, put -)
    "n_contracts_all", "gex_all_calls", "gex_all_puts", "net_gex_all", "gex_all_norm",
    # v3: qualita' dello snapshot: "ok" oppure motivi separati da ";"
    "quality",
]
STRIKE_FIELDS = [
    "snapshot_utc", "cboe_timestamp", "spot_parity", "root", "type", "strike",
    "bid", "ask", "iv", "delta", "gamma", "vega", "theta", "volume", "open_interest",
]


# ----------------------------------------------------------------------------
# utilita'
# ----------------------------------------------------------------------------
def num(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def fetch_chain(retries=3):
    req = urllib.request.Request(
        CBOE_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; 0dte-tracker/2.0)"}
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # rete, JSON, timeout...
            last_err = e
            print(f"Tentativo {attempt + 1}/{retries} fallito: {e}")
            time.sleep(2 * (attempt + 1))
    raise last_err


def parse_symbol(symbol):
    m = OCC_RE.match(symbol or "")
    if not m:
        return None
    d = m.group("date")
    expiry = datetime(2000 + int(d[0:2]), int(d[2:4]), int(d[4:6])).date()
    return m.group("root"), expiry, m.group("cp"), int(m.group("strike")) / 1000.0


def last_snapshot_utc(summary_path):
    """Legge il timestamp dell'ultima riga del summary (None se non esiste)."""
    if not os.path.isfile(summary_path):
        return None
    last = None
    with open(summary_path, newline="") as f:
        for line in f:
            if line.strip():
                last = line
    if not last or last.startswith("snapshot_utc"):
        return None
    try:
        return datetime.fromisoformat(last.split(",")[0])
    except ValueError:
        return None


def upgrade_header(path, fieldnames):
    """Se il file ha un'intestazione vecchia (meno colonne), la riscrive aggiungendo le colonne
    nuove in fondo, vuote per le righe gia' salvate. Le colonne e i valori esistenti non cambiano."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        old = reader.fieldnames or []
        if old == fieldnames:
            return
        if old != fieldnames[:len(old)]:
            raise SystemExit(f"Intestazione inattesa in {path}: non la tocco. Controllare a mano.")
        rows = list(reader)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
    print(f"{path}: aggiunte le colonne {fieldnames[len(old):]}")


def append_rows(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.isfile(path)
    if not new_file:
        upgrade_header(path, fieldnames)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        w.writerows(rows)


# ----------------------------------------------------------------------------
# controlli prima di scaricare
# ----------------------------------------------------------------------------
def should_run(now_utc, outdir=DATA_DIR, force=False):
    if force:
        return True, "forzato"
    now_et = now_utc.astimezone(ET)
    if now_et.weekday() >= 5:
        return False, f"weekend ({now_et:%a %H:%M} ET)"
    if not (MARKET_OPEN <= now_et.time() <= MARKET_CLOSE):
        return False, f"fuori orario di mercato ({now_et:%H:%M} ET)"
    last = last_snapshot_utc(os.path.join(outdir, SUMMARY_NAME))
    if last is not None:
        age = (now_utc - last).total_seconds()
        if 0 <= age < MIN_GAP_SECONDS:
            return False, f"ultimo snapshot di {age / 60:.1f} minuti fa (deduplica)"
    return True, "ok"


# ----------------------------------------------------------------------------
# elaborazione
# ----------------------------------------------------------------------------
def extract_contracts(chain_json, today=None):
    """Contratti con scadenza `today`; con today=None tutte le scadenze (gia' scadute escluse)."""
    out = []
    for o in chain_json.get("data", {}).get("options", []):
        p = parse_symbol(o.get("option"))
        if p is None:
            continue
        root, expiry, cp, strike = p
        if today is not None and expiry != today:
            continue
        out.append({
            "root": root, "expiry": expiry, "cp": cp, "strike": strike,
            "bid": num(o.get("bid")), "ask": num(o.get("ask")),
            "iv": num(o.get("iv")), "delta": num(o.get("delta")),
            "gamma": num(o.get("gamma")), "vega": num(o.get("vega")),
            "theta": num(o.get("theta")),
            "volume": num(o.get("volume"), 0.0), "oi": num(o.get("open_interest"), 0.0),
        })
    return out


def estimate_spot(contracts):
    """Spot sintetico via put-call parity sugli strike ATM: F = K + (C_mid - P_mid)."""
    pairs = {}
    for c in contracts:
        pairs.setdefault((c["root"], c["strike"]), {})[c["cp"]] = c
    cands = []
    for (_, k), d in pairs.items():
        if "C" in d and "P" in d:
            c, p = d["C"], d["P"]
            vals = (c["bid"], c["ask"], p["bid"], p["ask"])
            if all(v is not None and v > 0 for v in vals):
                cm = (c["bid"] + c["ask"]) / 2
                pm = (p["bid"] + p["ask"]) / 2
                cands.append((abs(cm - pm), k + cm - pm))
    if not cands:
        return None
    cands.sort()
    return statistics.median(f for _, f in cands[:5])


def atm_iv(contracts, spot):
    if spot is None:
        return None
    with_iv = [c for c in contracts if c["iv"] and c["iv"] > 0]
    if not with_iv:
        return None
    k = min({c["strike"] for c in with_iv}, key=lambda s: abs(s - spot))
    ivs = [c["iv"] for c in with_iv if c["strike"] == k]
    return sum(ivs) / len(ivs)


def gex(contracts, spot):
    """GEX in $ per 1% di movimento: gamma * OI * 100 * spot^2 * 0.01. Ritorna (call, put)."""
    gex_c = gex_p = 0.0
    if not spot:
        return gex_c, gex_p
    for c in contracts:
        oi = c["oi"] or 0.0
        if c["gamma"] is not None and oi > 0:
            g = c["gamma"] * oi * MULTIPLIER * spot ** 2 * 0.01
            if c["cp"] == "C":
                gex_c += g
            else:
                gex_p += g
    return gex_c, gex_p


def quality_flags(now_utc, spot, spot_cboe, gex_c, gex_p):
    """Motivi per cui lo snapshot non e' affidabile ("ok" se nessuno)."""
    flags = []
    if now_utc.astimezone(ET).time() < OPENING_UNRELIABLE_UNTIL:
        flags.append("apertura")
    if spot is None:
        flags.append("spot_mancante")
    elif spot_cboe and abs(spot - spot_cboe) / spot_cboe > SPOT_MISMATCH_PCT:
        flags.append("spot")
    if gex_c + gex_p == 0:
        flags.append("gex_zero")
    return ";".join(flags) if flags else "ok"


def summarize(chain_json, contracts, spot, now_utc, today, all_contracts=()):
    oi_c = oi_p = vol_c = vol_p = 0.0
    for c in contracts:
        oi, vol = c["oi"] or 0.0, c["volume"] or 0.0
        if c["cp"] == "C":
            oi_c += oi
            vol_c += vol
        else:
            oi_p += oi
            vol_p += vol
    gex_c, gex_p = gex(contracts, spot)
    gross = gex_c + gex_p
    iv_atm = atm_iv(contracts, spot)

    spot_cboe = num(chain_json.get("data", {}).get("current_price"))
    # tutte le scadenze: se manca lo spot da parity si usa il campo CBOE (segnalato in quality)
    spot_all = spot or spot_cboe
    live = [c for c in all_contracts if c["expiry"] >= today]
    gall_c, gall_p = gex(live, spot_all)
    gross_all = gall_c + gall_p
    return {
        "snapshot_utc": now_utc.replace(microsecond=0).isoformat(),
        "snapshot_et": now_utc.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S"),
        "cboe_timestamp": chain_json.get("timestamp"),
        "expiry": str(today),
        "spot_parity": round(spot, 2) if spot else "",
        "spot_cboe_field": chain_json.get("data", {}).get("current_price", ""),
        "n_contracts": len(contracts),
        "oi_calls": oi_c, "oi_puts": oi_p,
        "pc_oi_ratio": round(oi_p / oi_c, 4) if oi_c > 0 else "",
        "vol_calls": vol_c, "vol_puts": vol_p,
        "pc_vol_ratio": round(vol_p / vol_c, 4) if vol_c > 0 else "",
        "iv_atm": round(iv_atm, 4) if iv_atm else "",
        "gex_calls": round(gex_c), "gex_puts": round(gex_p),
        "net_gex": round(gex_c - gex_p),
        "gex_norm": round((gex_c - gex_p) / gross, 4) if gross > 0 else "",
        "n_contracts_all": len(live),
        "gex_all_calls": round(gall_c), "gex_all_puts": round(gall_p),
        "net_gex_all": round(gall_c - gall_p),
        "gex_all_norm": round((gall_c - gall_p) / gross_all, 4) if gross_all > 0 else "",
        "quality": quality_flags(now_utc, spot, spot_cboe, gex_c, gex_p),
    }


def strike_rows(contracts, spot, now_utc, cboe_ts):
    if spot is None:
        return []
    rows = []
    for c in contracts:
        if abs(c["strike"] - spot) / spot > BAND_PCT:
            continue
        active = (c["bid"] or 0) > 0 or (c["ask"] or 0) > 0 or (c["volume"] or 0) > 0 or (c["oi"] or 0) > 0
        if not active:
            continue
        rows.append({
            "snapshot_utc": now_utc.replace(microsecond=0).isoformat(),
            "cboe_timestamp": cboe_ts, "spot_parity": round(spot, 2),
            "root": c["root"], "type": c["cp"], "strike": c["strike"],
            "bid": c["bid"], "ask": c["ask"], "iv": c["iv"], "delta": c["delta"],
            "gamma": c["gamma"], "vega": c["vega"], "theta": c["theta"],
            "volume": c["volume"], "open_interest": c["oi"],
        })
    return rows


def process(chain_json, now_utc, outdir=DATA_DIR):
    today = now_utc.astimezone(ET).date()
    all_contracts = extract_contracts(chain_json)
    contracts = [c for c in all_contracts if c["expiry"] == today]
    if not contracts:
        print(f"Nessun contratto con scadenza {today}: niente da salvare.")
        return None
    spot = estimate_spot(contracts)
    summary = summarize(chain_json, contracts, spot, now_utc, today, all_contracts)
    rows = strike_rows(contracts, spot, now_utc, chain_json.get("timestamp"))
    append_rows(os.path.join(outdir, SUMMARY_NAME), SUMMARY_FIELDS, [summary])
    if rows:
        append_rows(os.path.join(outdir, f"strikes_{today}.csv"), STRIKE_FIELDS, rows)
    print(f"Salvato snapshot: {len(contracts)} contratti 0DTE, spot~{summary['spot_parity']}, "
          f"{len(rows)} righe per strike, net_gex={summary['net_gex']}, "
          f"net_gex_all={summary['net_gex_all']}, quality={summary['quality']}")
    return summary


def main():
    force = "--force" in sys.argv
    now_utc = datetime.now(timezone.utc)
    ok, reason = should_run(now_utc, force=force)
    if not ok:
        print(f"Salto l'esecuzione: {reason}")
        return 0
    chain_json = fetch_chain()
    process(chain_json, now_utc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
