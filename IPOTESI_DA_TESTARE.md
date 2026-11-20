# Ipotesi da testare (fissate prima di guardare i dati nuovi)

Scritte il 27/10/2026. Le regole qui sotto vanno applicate **così come sono**: cambiarle dopo aver
visto i risultati rende il test inutile.

## H1: il segno del GEX 0DTE anticipa l'ampiezza del movimento intraday

**Idea.** Con GEX netto negativo i dealer amplificano i movimenti, con GEX positivo li smorzano.
Quindi il segno del GEX dice *quanto* si muoverà SPX, non *dove*.

**Cosa si è visto nei giorni di scoperta (05/10 – 23/10/2026, 14 giorni utili).**
Questi giorni hanno generato l'ipotesi e **non** valgono come prova.

| Regime GEX alle 10:00 | giorni | range medio 10:00→chiusura | movimento medio nei 15 min successivi |
|---|---|---|---|
| positivo | 6 | 0,56% | 5,0 bp |
| negativo | 8 | 0,71% | 8,3 bp |

- correlazione `gex_norm` alle 10:00 / range del giorno: −0,45
- correlazione con il rendimento del giorno (direzione): circa 0

### Regole del test

- **Campione di verifica:** solo i giorni **dal 26/10/2026 in poi**.
- **Quando:** a partire da circa **40 giorni di verifica** (indicativamente gennaio 2027).
  Prima solo controlli descrittivi, senza conclusioni.
- **Dati:** `data/summary_0dte.csv`, solo i giorni con almeno 20 snapshot.
- **Segnale:** `gex_norm` del primo snapshot con orario ET ≥ 10:00 e `quality` = `ok`.
  - GEX positivo se `gex_norm > 0`, negativo se `gex_norm < 0`.
- **Esito:** `range_pct` = (max − min di `spot_parity` dalle 10:00 alla chiusura) / spot alle 10:00 × 100.
- **Test principale:** Mann–Whitney a una coda (range con GEX negativo > range con GEX positivo), con α = 0,05.
- **Test di contorno (non decisivi):**
  1. correlazione di Spearman tra `gex_norm` alle 10:00 e `range_pct` (attesa negativa);
  2. regressione di `range_pct` su `gex_norm` con `iv_atm` alle 10:00 come controllo: serve a capire se il GEX aggiunge informazione rispetto alla IV, che a sua volta anticipa la volatilità (correlazione 0,54 nei giorni di scoperta);
  3. lo stesso test con `gex_all_norm` (tutte le scadenze), disponibile dal 15/10.
- **Ipotesi confermata se:** il test principale è significativo **e** il segno del controllo 2 resta negativo.

### Aggiornamento 20/11/2026: raccolta interrotta, test su meno giorni

- Dal 20/11/2026 alle 14:30 UTC CBOE reindirizza il feed gratuito (`cdn.cboe.com`) a
  `cdn-api.cboe.com`, che sta dietro la protezione anti-bot di Cloudflare ("Attention Required!") e
  risponde 403 al collettore. È un blocco voluto: non lo si aggira.
- Una fonte ufficiale, gratuita e senza registrazione con OI e IV per strike non esiste. Si è
  scelto quindi di **fermare la raccolta** e di tenere i dati raccolti.
- **Ultimo giorno di dati:** 19/11/2026. **Giorni di verifica disponibili:** 19 (dal 26/10 al 19/11),
  invece dei circa 40 previsti.
- **Cambio di regola, deciso prima di guardare i risultati e solo per mancanza di dati:** il test
  si fa sui 19 giorni di verifica disponibili, con le stesse regole qui sopra. Il risultato va
  letto come **indicativo**: con 19 giorni si vede solo un effetto forte (correlazione intorno a
  −0,5 o più), non uno medio.
- **Trasparenza:** il 04/11/2026 si è guardato una volta, in modo informale, l'andamento dei primi 8
  giorni di verifica (nessun effetto visibile). Le regole non sono state cambiate dopo quel controllo.

### Limiti noti

- L'OI CBOE è fisso per tutta la giornata: il GEX intraday cambia solo per spot e gamma.
- Il segno assume dealer lunghi sulle call e corti sulle put (convenzione standard, non verificabile).
- I giorni di scadenza mensile includono le SPX AM già scadute: OI e put/call di quei giorni sono gonfiati.
- La volatilità realizzata stimata ogni 15 minuti è sottostimata: non va confrontata alla pari con la IV.

## Idee secondarie (scartate o da rivedere)

- **Effetto calamita sullo strike con OI massimo:** non regge (chiusura in mediana a 156 punti da quello strike).
- **Chiusura dentro put wall / call wall:** 15 su 15, ma i muri distano 1–3% dallo spot, quindi non è informativo.
- **Volume per strike al posto dell'OI** per stimare le posizioni aperte in giornata: da sviluppare.
