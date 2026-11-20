"""Studio sul rientro del VIX dopo un superamento di 30.

Regole fissate in PREREGISTRAZIONE.md. Non modificare le soglie dopo aver visto i risultati.

Uso:
    python3 vix_studio/studio_vix.py vix_studio/dati/vix_daily.csv
Input: CSV con colonne date,close (date AAAA-MM-GG, chiusura giornaliera del VIX).
Output: riepilogo a schermo e vix_studio/risultati/{episodi.csv,riepilogo.txt}.
Solo libreria standard.
"""

import csv
import math
import os
import statistics
import sys

START_SOGLIA = 30.0      # inizio episodio: chiusura >= 30
RIARMO_SOGLIA = 25.0     # l'episodio si riarma solo quando la chiusura torna < 25
H = 20                   # orizzonte in giorni di borsa
SOGLIE_RIENTRO = (25.0, 20.0)   # 25 = principale, 20 = secondaria
SOGLIE_ESCALATION = (40.0, 50.0)  # 40 = secondaria, 50 = secondaria
FINESTRE = (5, 10, 20)


def leggi_serie(percorso):
    righe = []
    with open(percorso, newline="", encoding="utf-8") as f:
        lettore = csv.DictReader(f)
        for r in lettore:
            d = (r.get("date") or "").strip()
            v = (r.get("close") or "").strip()
            if not d or v in ("", "."):
                continue  # FRED usa "." per i giorni senza dato
            try:
                righe.append((d, float(v)))
            except ValueError:
                continue
    righe.sort(key=lambda x: x[0])
    date = [d for d, _ in righe]
    chiusure = [c for _, c in righe]
    return date, chiusure


def trova_episodi(date, chiusure):
    """Inizio episodio alla prima chiusura >= 30 mentre lo stato è armato.
    Disarmo dopo l'inizio, riarmo solo quando la chiusura torna < 25."""
    episodi = []
    armato = True
    for i, c in enumerate(chiusure):
        if armato and c >= START_SOGLIA:
            episodi.append(i)
            armato = False
        elif not armato and c < RIARMO_SOGLIA:
            armato = True
    return episodi


def esiti_episodio(i, date, chiusure):
    n = len(chiusure)
    completo = i + H <= n - 1
    finestra = chiusure[i + 1: i + H + 1]
    rientri = {}
    for soglia in SOGLIE_RIENTRO:
        giorno = None
        for k, c in enumerate(finestra, start=1):
            if c < soglia:
                giorno = k
                break
        rientri[soglia] = giorno
    picco = max(finestra) if finestra else float("nan")
    giorno_picco = (finestra.index(picco) + 1) if finestra else None
    return {
        "data_inizio": date[i],
        "chiusura_inizio": chiusure[i],
        "completo": completo,
        "giorni_rientro_25": rientri[25.0],
        "giorni_rientro_20": rientri[20.0],
        "picco_20g": round(picco, 2) if finestra else None,
        "giorno_picco": giorno_picco,
        "escalation_40": picco >= 40 if finestra else None,
        "escalation_50": picco >= 50 if finestra else None,
    }


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margine = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centro - margine), min(1.0, centro + margine))


def riepilogo_soglia(episodi_completi, soglia):
    chiave = "giorni_rientro_25" if soglia == 25.0 else "giorni_rientro_20"
    n = len(episodi_completi)
    righe = [f"Soglia di rientro < {soglia:g} (n = {n} episodi completi)"]
    if n == 0:
        return "\n".join(righe + ["  nessun episodio completo"])
    for w in FINESTRE:
        k = sum(1 for e in episodi_completi if e[chiave] is not None and e[chiave] <= w)
        lo, hi = wilson(k, n)
        righe.append(f"  rientro entro {w:>2} giorni: {k}/{n} = {100*k/n:5.1f}%  (IC 95% Wilson {100*lo:4.1f}-{100*hi:4.1f}%)")
    giorni = [e[chiave] for e in episodi_completi if e[chiave] is not None]
    if giorni:
        righe.append(f"  mediana giorni di rientro (solo rientrati, {len(giorni)}): {statistics.median(giorni):.1f}")
    else:
        righe.append("  nessun episodio rientrato nei 20 giorni")
    return "\n".join(righe)


def riepilogo_escalation(episodi_completi):
    n = len(episodi_completi)
    if n == 0:
        return "Escalation: nessun episodio completo"
    righe = [f"Escalation (n = {n} episodi completi)"]
    for s in SOGLIE_ESCALATION:
        k = sum(1 for e in episodi_completi if e["picco_20g"] is not None and e["picco_20g"] >= s)
        lo, hi = wilson(k, n)
        righe.append(f"  picco nei 20 giorni >= {s:g}: {k}/{n} = {100*k/n:5.1f}%  (IC 95% {100*lo:4.1f}-{100*hi:4.1f}%)")
    picchi = [e["picco_20g"] for e in episodi_completi if e["picco_20g"] is not None]
    righe.append(f"  mediana del picco nei 20 giorni: {statistics.median(picchi):.1f}")
    return "\n".join(righe)


def main():
    if len(sys.argv) != 2:
        print("Uso: python3 vix_studio/studio_vix.py <vix_daily.csv>")
        sys.exit(1)
    date, chiusure = leggi_serie(sys.argv[1])
    if len(chiusure) < H + 2:
        print("Serie troppo corta")
        sys.exit(1)

    idx = trova_episodi(date, chiusure)
    tutti = [esiti_episodio(i, date, chiusure) for i in idx]
    completi = [e for e in tutti if e["completo"]]
    in_corso = [e for e in tutti if not e["completo"]]

    blocchi = [
        f"Dati: {date[0]} -> {date[-1]}, {len(chiusure)} giorni",
        f"Episodi totali (chiusura >= {START_SOGLIA:g}, con riarmo < {RIARMO_SOGLIA:g}): {len(tutti)}",
        f"  completi (20 giorni osservati): {len(completi)}",
        f"  in corso / finestra incompleta, esclusi dai tassi: {len(in_corso)}",
        "",
        riepilogo_soglia(completi, 25.0),
        "",
        riepilogo_soglia(completi, 20.0),
        "",
        riepilogo_escalation(completi),
    ]
    testo = "\n".join(blocchi)
    print(testo)

    cartella = os.path.join(os.path.dirname(os.path.abspath(__file__)), "risultati")
    os.makedirs(cartella, exist_ok=True)
    with open(os.path.join(cartella, "riepilogo.txt"), "w", encoding="utf-8") as f:
        f.write(testo + "\n")
    if tutti:
        with open(os.path.join(cartella, "episodi.csv"), "w", newline="", encoding="utf-8") as f:
            scrittore = csv.DictWriter(f, fieldnames=list(tutti[0].keys()))
            scrittore.writeheader()
            scrittore.writerows(tutti)


if __name__ == "__main__":
    main()
