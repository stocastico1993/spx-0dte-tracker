# Studio VIX: quando rientra dopo aver superato 30

Scritto il 20/11/2026, **prima di aver visto qualsiasi serie storica del VIX** in questo studio.
Le regole qui sotto vanno applicate così come sono. Se cambiano dopo aver visto i risultati,
il test non vale più.

Script: `python3 vix_studio/studio_vix.py vix_studio/dati/vix_daily.csv`

## Domanda

Dopo che il VIX chiude per la prima volta sopra 30 (un "episodio"), quanto spesso e quanto presto
torna sotto 25 (e sotto 20)? Quanto spesso invece sale ancora, fino a 40 o oltre?

## Dati

- Serie: chiusura giornaliera del VIX (CBOE Volatility Index), una riga per giorno di borsa.
- File atteso: `vix_studio/dati/vix_daily.csv` con colonne `date,close` (date in formato AAAA-MM-GG).
- Fonte: da scaricare a mano da una fonte pubblica (ad esempio FRED, serie VIXCLS, oppure il sito
  CBOE). Il container non può raggiungere FRED per policy di rete, quindi il file arriva dall'utente.
- Il periodo va dal primo dato disponibile fino all'ultimo giorno utile. Non si esclude nessun anno.

## Definizione di episodio (fissata)

- **Inizio episodio:** il primo giorno in cui la chiusura è ≥ 30, quando lo stato è "armato".
- Dopo un inizio, lo stato diventa "disarmato" finché la chiusura non torna **< 25**. Solo allora
  si riarma. Così una serie di giorni sopra 30 conta come un solo episodio.
- Gli episodi ancora in corso alla fine dei dati si contano a parte e non entrano nei tassi.

## Esiti (per ogni episodio)

Orizzonte di osservazione: **H = 20 giorni di borsa** dopo l'inizio.

- `giorni_rientro_25`: primo giorno (1..20) con chiusura < 25. Se non succede in 20 giorni: non
  rientrato.
- `giorni_rientro_20`: stessa cosa con soglia 20 (secondaria).
- `picco_20g`: chiusura massima nei 20 giorni dopo l'inizio, con il giorno in cui è stata raggiunta.
- `escalation`: sì se `picco_20g` ≥ 40 (soglia fissata, secondaria: ≥ 50).

## Statistiche riportate

- **Principale:** quota di episodi con rientro sotto 25 entro 5, 10 e 20 giorni, con intervallo di
  confidenza di Wilson al 95%.
- Mediana dei giorni di rientro, solo tra gli episodi rientrati.
- Quota di episodi con escalation (picco ≥ 40), e mediana del picco.
- Stesse statistiche per la soglia 20 (secondaria).
- Elenco completo degli episodi in `vix_studio/risultati/episodi.csv`, con tutti i casi, compresi i
  non rientrati e le escalation. Non si scelgono episodi a mano.

## Limiti da tenere presenti

- Gli episodi sopra 30 sono pochi (pochi eventi reali di stress, come 2008, 2011, 2015, 2018, 2020,
  2022). Gli intervalli di confidenza saranno ampi: il risultato va letto come un ordine di grandezza.
- Gli episodi non sono indipendenti: periodi di stress lunghi generano più casi correlati.
- Lo studio non dice niente sul prezzo delle opzioni sul VIX, né sul P&L di una put o di uno spread.
  Dà solo la frequenza e i tempi del movimento del VIX.
- Anche con una buona frequenza di rientro, un picco intermedio a 40 o più può far perdere su una
  posizione short VIX con stop o senza copertura adeguata: per questo si riporta anche l'escalation.
