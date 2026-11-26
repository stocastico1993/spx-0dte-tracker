"""Riduce i file Parquet delle opzioni (un file per anno) a totali giornalieri.

Uso, sul proprio computer, dopo aver scaricato i file veri (non i puntatori Git LFS):
    pip install pandas pyarrow
    python3 aggregate_flow.py /percorso/data/parquet_spy spy_daily_flow.csv

Input: cartella con options_AAAA.parquet. Legge solo le colonne date, type, volume,
open_interest (poca memoria).
Output: CSV con una riga per giorno:
    date, call_volume, put_volume, call_oi, put_oi
Il CSV è piccolo (poche migliaia di righe) e si può caricare in chat.
"""

import glob
import sys

import pandas as pd


def main():
    if len(sys.argv) != 3:
        print("Uso: python3 aggregate_flow.py <cartella_parquet> <output.csv>")
        sys.exit(1)
    cartella, uscita = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(f"{cartella}/options_*.parquet"))
    if not files:
        print("Nessun file options_*.parquet trovato in", cartella)
        sys.exit(1)

    pezzi = []
    for f in files:
        df = pd.read_parquet(f, columns=["date", "type", "volume", "open_interest"])
        # type può essere 'call'/'put' oppure 'C'/'P': teniamo la prima lettera
        df["type"] = df["type"].astype(str).str.lower().str[0]
        g = df.groupby(["date", "type"])[["volume", "open_interest"]].sum().unstack("type")
        g.columns = [f"{a}_{b}" for a, b in g.columns]
        pezzi.append(g.reset_index())
        print(f, "ok", len(g), "giorni")

    res = pd.concat(pezzi).sort_values("date")
    res = res.rename(columns={
        "volume_c": "call_volume", "volume_p": "put_volume",
        "open_interest_c": "call_oi", "open_interest_p": "put_oi",
    })
    res.to_csv(uscita, index=False)
    print("Scritto", uscita, "con", len(res), "righe")


if __name__ == "__main__":
    main()
