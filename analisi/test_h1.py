"""
Test dell'ipotesi H1 di IPOTESI_DA_TESTARE.md, con le regole fissate prima di vedere i dati:
il segno del GEX 0DTE alle 10:00 ET anticipa l'ampiezza del movimento dalle 10:00 alla chiusura.

Uso (dalla cartella principale del repo, serve pandas):
    python3 analisi/test_h1.py
"""
import numpy as np
import pandas as pd

DATI = "data/summary_0dte.csv"
INIZIO_VERIFICA = "2026-10-26"
INIZIO_SCOPERTA = "2026-10-05"
MIN_SNAPSHOT = 20
PERMUTAZIONI = 100_000
BOOTSTRAP = 20_000
ALFA = 0.05


def giorni(s):
    """Una riga per giorno: segnale al primo snapshot ok dalle 10:00 ET, range dalle 10:00 alla chiusura."""
    righe = []
    for giorno, g in s.groupby("expiry"):
        if len(g) < MIN_SNAPSHOT:
            continue
        dopo10 = g[(g.t.dt.hour * 60 + g.t.dt.minute >= 600) & g.spot_parity.notna()].sort_values("t")
        # prima del 15/10 la colonna quality non esiste (vuota): vale come ok se lo spot c'e'
        ok = dopo10[(dopo10.quality == "ok") | dopo10.quality.isna()]
        if ok.empty:
            continue
        e = ok.iloc[0]
        righe.append({"giorno": giorno, "gex_norm": e.gex_norm, "gex_all_norm": e.gex_all_norm,
                      "iv_atm": e.iv_atm, "range_pct": 100 * (dopo10.spot_parity.max() - dopo10.spot_parity.min())
                      / e.spot_parity})
    return pd.DataFrame(righe)


def mann_whitney(neg, pos, rng):
    """U di neg > pos e p a una coda da permutazioni."""
    def u(a, b):
        return sum((x > y) + 0.5 * (x == y) for x in a for y in b)
    tutti, k, oss = np.r_[neg, pos], len(neg), u(neg, pos)
    perm = [u(*np.split(rng.permutation(tutti), [k])) for _ in range(PERMUTAZIONI // 10)]
    return oss, np.mean(np.array(perm) >= oss)


def spearman(x, y, rng):
    rx, ry = pd.Series(x).rank().values, pd.Series(y).rank().values
    r = np.corrcoef(rx, ry)[0, 1]
    return r, np.mean([np.corrcoef(rx, rng.permutation(ry))[0, 1] <= r for _ in range(PERMUTAZIONI // 10)])


def regressione(d, rng):
    X = np.c_[np.ones(len(d)), d.gex_norm, d.iv_atm]
    y = d.range_pct.values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    boot = []
    for _ in range(BOOTSTRAP):
        i = rng.integers(0, len(d), len(d))
        boot.append(np.linalg.lstsq(X[i], y[i], rcond=None)[0][1])
    return b, np.percentile(boot, [5, 95])


def analizza(d, nome, rng):
    print(f"\n=== {nome}: {len(d)} giorni ({d.giorno.min()} .. {d.giorno.max()})")
    neg, pos = d[d.gex_norm < 0].range_pct.values, d[d.gex_norm > 0].range_pct.values
    u, p = mann_whitney(neg, pos, rng)
    print(f"  GEX negativo: {len(neg)} giorni, range medio {neg.mean():.3f}% (mediana {np.median(neg):.3f}%)")
    print(f"  GEX positivo: {len(pos)} giorni, range medio {pos.mean():.3f}% (mediana {np.median(pos):.3f}%)")
    print(f"  TEST PRINCIPALE Mann-Whitney (neg > pos): U = {u:.1f} su {len(neg) * len(pos)}, p = {p:.3f}")
    r, pr = spearman(d.gex_norm, d.range_pct, rng)
    print(f"  contorno 1, Spearman gex_norm / range: {r:+.2f} (p a una coda {pr:.3f})")
    b, ic = regressione(d, rng)
    print(f"  contorno 2, range ~ gex_norm + iv_atm: coefficiente GEX {b[1]:+.3f} (IC 90% {ic[0]:+.3f} .. {ic[1]:+.3f}),"
          f" coefficiente IV {b[2]:+.2f}")
    a = d[d.gex_all_norm.notna()]
    if len(a) >= 5:
        na, pa = a[a.gex_all_norm < 0].range_pct.values, a[a.gex_all_norm > 0].range_pct.values
        ua, pua = mann_whitney(na, pa, rng)
        ra, pra = spearman(a.gex_all_norm, a.range_pct, rng)
        print(f"  contorno 3, gex_all_norm: {len(na)} neg / {len(pa)} pos, Mann-Whitney p = {pua:.3f},"
              f" Spearman {ra:+.2f} (p {pra:.3f})")
    print(f"  correlazione gex_norm / iv_atm: {d.gex_norm.corr(d.iv_atm):+.2f}")
    return p, b[1]


def main():
    s = pd.read_csv(DATI)
    s["t"] = pd.to_datetime(s.snapshot_et)
    d = giorni(s)
    rng = np.random.default_rng(0)
    print(d[d.giorno >= INIZIO_VERIFICA].round(3).to_string(index=False))
    p, coef = analizza(d[d.giorno >= INIZIO_VERIFICA], "VERIFICA (decide il test)", rng)
    analizza(d[(d.giorno >= INIZIO_SCOPERTA) & (d.giorno < INIZIO_VERIFICA)], "scoperta (solo confronto)", rng)
    esito = "CONFERMATA" if p < ALFA and coef < 0 else "NON CONFERMATA"
    print(f"\nIpotesi H1 {esito}: test principale p = {p:.3f} (soglia {ALFA}), coefficiente del controllo {coef:+.3f}")


if __name__ == "__main__":
    main()
