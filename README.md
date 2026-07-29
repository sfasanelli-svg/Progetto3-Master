# Progetto EV Charge Desert — Scraping 3 (Vector Tile, definitivo)

Ripartenza pulita dello scraping a vector tile ([Progetto2-Master](https://github.com/sfasanelli-svg/Progetto2-Master)),
dopo aver trovato e corretto un bug che posizionava male ogni punto raccolto.

## Il bug (in breve)

`02_monitoraggio_traffico_tile.py` usa la libreria `mapbox_vector_tile` per
decodificare i tile TomTom, poi converte le coordinate pixel del tile in
lon/lat con `tile_px_to_lonlat()`. Quella funzione si aspetta la coordinata Y
**grezza** del tile (convenzione MVT, Y verso il basso). Ma
`mapbox_vector_tile.decode()`, di default (`y_coord_down=False`), **inverte
già** l'asse Y prima di restituire i punti (per dare coordinate "in stile
GeoJSON", Y verso l'alto). Il risultato era un **doppio flip**: ogni punto
veniva riflesso rispetto al centro verticale del proprio tile.

**Impatto verificato sui dati raccolti dal 22/07 al 28/07 2026**
(`Progetto2-Master`, non toccato, resta come riferimento):
- Spostamento medio ~344 m, fino a 858 m
- Solo il 31,6% delle righe "dentro_sezione" restavano davvero nella sezione
  a cui erano assegnate, una volta corretta la posizione
- ~47% dei dati non appartenevano a **nessuna** delle 50 sezioni monitorate

**Fix**: `mapbox_vector_tile.decode(r.content, default_options={"y_coord_down": True})`
in `02_monitoraggio_traffico_tile.py`. Verificato con una chiamata reale
all'API e conferma incrociata su OpenStreetMap (Nominatim): un segmento
"Motorway" ora ricade esattamente su "Tangenziale Ovest di Milano" invece che
in un parcheggio a 130-750m di distanza.

## Cosa contiene questa cartella

Stessa pipeline di `Progetto2-Master`, script 01-08 (vedi commenti nei singoli
file), con **solo il fix sopra applicato**. Nessun dato storico: si riparte
da zero, `traffico_tile_serie_storica_milano.csv` verrà creato al primo
avvio dello scraper.

## Setup da completare (fuori dal codice)

1. Creare il repository GitHub vuoto (fatto da chi esegue il setup)
2. Aggiungere il secret `TOMTOM_API_KEY` nelle impostazioni del repository
   (Settings → Secrets and variables → Actions)
3. Creare un nuovo job su [cron-job.org](https://cron-job.org) che chiami
   l'API GitHub (`workflow_dispatch`) su questo repository, con lo stesso
   Personal Access Token già usato per gli altri due progetti
