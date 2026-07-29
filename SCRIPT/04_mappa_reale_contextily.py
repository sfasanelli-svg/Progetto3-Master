# -*- coding: utf-8 -*-
"""
Step 4 del progetto parallelo (vector tiles) - mappa statica con basemap reale.

Stessa logica di 03_grafico_esempio_sezione.py (congestione massima per
segmento, soglia di robustezza a MIN_LETTURE, evidenza del segmento piu'
critico), ma sovrapposta a una mappa reale (stile CartoDB Positron via
contextily) invece che a un grafico a dispersione astratto: pensata per
essere incollata direttamente in una slide di presentazione.

Scala colore fissata (0-1, non sul massimo della singola sezione) cosi'
questa mappa resta confrontabile, slide dopo slide, con
07_mappa_aggregata_50_sezioni.py, che usa la stessa convenzione.

Richiede una connessione internet (contextily scarica le tile della mappa
al volo). I dati vengono riproiettati in Web Mercator (EPSG:3857), il
sistema di riferimento richiesto dalle tile.

Output: mappa_reale_<comune>.png
"""

from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D

CARTELLA_SCRIPT = Path(__file__).resolve().parent
IN_CSV = CARTELLA_SCRIPT / "traffico_tile_serie_storica_milano.csv"
IN_GEOJSON = CARTELLA_SCRIPT / "top50_sezioni_critiche_milano.geojson"

SEZ_ESEMPIO = 151460002842  # cambiare qui per un'altra sezione (deve combaciare con
                            # la sezione piu' critica evidenziata in 07_mappa_aggregata_50_sezioni.py)
MIN_LETTURE = 5
N_CANDIDATI = 3  # quanti segmenti evidenziare: tante quante le colonnine da installare in questa sezione
BOZZA = True  # metti a False quando la raccolta dati e' conclusa: toglie la dicitura "preview, da confermare"

INK = "#2b2b2b"
MUTED = "#5a5a5a"
ACCENT = "#c0392b"


def main():
    df = pd.read_csv(IN_CSV)
    sezioni = gpd.read_file(IN_GEOJSON)

    df["lat_r"] = df["lat"].round(5)
    df["lon_r"] = df["lon"].round(5)

    sez = df[df["SEZ2011"] == SEZ_ESEMPIO].copy()
    if sez.empty:
        raise ValueError(f"Nessun dato per SEZ2011={SEZ_ESEMPIO}")
    poligono = sezioni[sezioni["SEZ2011"].astype(int) == SEZ_ESEMPIO].iloc[0]
    comune = poligono["COMUNE"]

    per_segmento = sez.groupby(["lat_r", "lon_r", "road_type"]).agg(
        congestione_max=("congestione", "max"), n_letture=("congestione", "size")
    ).reset_index()

    # L'assegnazione di un segmento alla sezione (02_monitoraggio_traffico_tile.py) usa
    # il poligono bufferizzato di 50m, non il confine esatto: un segmento puo' quindi
    # risultare "assegnato" pur trovandosi, in realta', dentro una sezione confinante.
    # Suggerire di installarci una colonnina di QUESTA sezione sarebbe fuorviante in una
    # slide, quindi si tengono solo i segmenti geometricamente dentro il confine esatto.
    punti = gpd.GeoDataFrame(
        per_segmento, geometry=gpd.points_from_xy(per_segmento["lon_r"], per_segmento["lat_r"]), crs="EPSG:4326")
    per_segmento = per_segmento[punti.within(poligono.geometry).to_numpy()].copy()

    # a parita' di congestione massima il tie-break e' il numero di letture (il
    # segmento con piu' osservazioni a supporto e' il dato piu' affidabile), non
    # l'ordine arbitrario del groupby - vedi anche 03/05/06
    robusti = per_segmento[per_segmento["n_letture"] >= MIN_LETTURE].sort_values(
        ["congestione_max", "n_letture"], ascending=[False, False])
    non_robusti = per_segmento[per_segmento["n_letture"] < MIN_LETTURE]
    if robusti.empty:
        raise ValueError(f"Nessun segmento robusto dentro il confine esatto per SEZ2011={SEZ_ESEMPIO}, "
                          "serve piu' tempo di raccolta")

    if len(robusti) < N_CANDIDATI:
        print(f"Attenzione: solo {len(robusti)} segmenti robusti dentro il confine esatto "
              f"(< N_CANDIDATI={N_CANDIDATI}); evidenzio quelli disponibili.")
    top_n = robusti.head(N_CANDIDATI)

    # ------------------------------------------------------------ riproiezione in Web Mercator
    gdf_robusti = gpd.GeoDataFrame(
        robusti, geometry=gpd.points_from_xy(robusti["lon_r"], robusti["lat_r"]), crs="EPSG:4326"
    ).to_crs("EPSG:3857")
    gdf_non_robusti = gpd.GeoDataFrame(
        non_robusti, geometry=gpd.points_from_xy(non_robusti["lon_r"], non_robusti["lat_r"]), crs="EPSG:4326"
    ).to_crs("EPSG:3857")
    poligono_3857 = gpd.GeoSeries([poligono.geometry], crs="EPSG:4326").to_crs("EPSG:3857")
    top_n_3857 = gpd.GeoDataFrame(
        top_n, geometry=gpd.points_from_xy(top_n["lon_r"], top_n["lat_r"]), crs="EPSG:4326"
    ).to_crs("EPSG:3857")

    cmap = plt.get_cmap("YlOrRd")
    # scala fissa 0-1 (non sul massimo di questa sezione): rende il colore
    # confrontabile con altre mappe della stessa serie (es. 07_mappa_aggregata_50_sezioni.py)
    norm = Normalize(vmin=0, vmax=1)

    fig, ax = plt.subplots(figsize=(10, 10), dpi=200)

    poligono_3857.plot(ax=ax, facecolor="none", edgecolor=INK, linewidth=2, zorder=2)

    # estensione della mappa fissata sul poligono della sezione (con margine), non
    # sui punti tracciati: dopo aver tolto i segmenti fuori confine, i punti rimasti
    # sono spesso concentrati in un angolo, e lasciare che contextily/geopandas
    # calcolino l'estensione sulla base dei soli punti restringe lo zoom in modo
    # imprevedibile (tagliando il perimetro e spingendo le etichette fuori bordo)
    minx, miny, maxx, maxy = poligono_3857.total_bounds
    margine = 0.18 * max(maxx - minx, maxy - miny)
    ax.set_xlim(minx - margine, maxx + margine)
    ax.set_ylim(miny - margine, maxy + margine)

    if len(gdf_non_robusti):
        gdf_non_robusti.plot(ax=ax, color="#bdbdbd", markersize=22, alpha=0.7, zorder=3,
                              label=f"< {MIN_LETTURE} letture (dato insufficiente)")

    dim_min, dim_max = 30, 30 + 60 * 1.5  # estremi usati sotto per la legenda dimensioni
    sizes = 30 + gdf_robusti["n_letture"].clip(upper=60) * 1.5
    gdf_robusti.plot(ax=ax, column="congestione_max", cmap=cmap, vmin=0, vmax=norm.vmax,
                      markersize=sizes, edgecolor="white", linewidth=0.6, zorder=4)

    ORDINALI = ["1°", "2°", "3°", "4°", "5°"]
    # offset relativo al punto STESSO (non una posizione assoluta sulla mappa): i
    # candidati sono quasi sempre vicinissimi fra loro (stesso incrocio/strada), quindi
    # un ancoraggio assoluto lontano (es. in un angolo fisso) costringerebbe la freccia
    # ad attraversare altri punti colorati non correlati, illeggibile. Restando vicini
    # al proprio punto (offset crescente solo in verticale) le frecce restano corte e
    # le 3 etichette si impilano leggibili una sopra l'altra accanto al cluster
    n_top = len(top_n)
    for i, (_, riga) in enumerate(top_n.iterrows()):
        punto = top_n_3857.geometry.iloc[i]
        raggio = 600 - i * 110  # cerchio leggermente piu' piccolo per il 2°, 3°... (gerarchia visiva)
        ax.scatter([punto.x], [punto.y], marker="o", facecolor="none", edgecolor=ACCENT,
                   s=raggio, linewidth=3 - i * 0.4, zorder=5)
        # il 1° in classifica va in cima alla pila (dy maggiore), il 3° in fondo (piu'
        # vicino al cluster): ordine di lettura dall'alto verso il basso 1-2-3
        dy = 55 + (n_top - 1 - i) * 48
        ax.annotate(f"{ORDINALI[i]} segmento più critico", (punto.x, punto.y),
                    xytext=(65, dy), textcoords="offset points", ha="left", va="bottom",
                    fontsize=11.5, color=ACCENT, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")],
                    arrowprops=dict(arrowstyle="-", color=ACCENT, linewidth=1.3,
                                     shrinkA=0, shrinkB=8,
                                     connectionstyle="arc3,rad=0.12"))

    # basemap reale (richiede internet)
    ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron, zoom=16)

    ax.set_axis_off()
    ax.set_title(f"Congestione massima per segmento — {comune}", fontsize=15,
                 color=INK, loc="left", pad=12, fontweight="bold")

    cbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label(f"congestione massima (min. {MIN_LETTURE} letture)", fontsize=10, color=MUTED)

    # legenda dimensione punti (n. letture): proxy separati dal colore, che
    # codifica solo la congestione — cosi' le due codifiche restano leggibili
    riferimenti_letture = [5, 20, 60]
    proxy_dimensioni = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="#bdbdbd",
               markeredgecolor="white", markeredgewidth=0.6,
               markersize=((30 + min(n, 60) * 1.5) ** 0.5) * 0.62,
               label=f"{n} letture" + (" o più" if n == max(riferimenti_letture) else ""))
        for n in riferimenti_letture
    ]
    legenda_dato = ax.legend(handles=[Line2D([0], [0], marker="o", linestyle="none",
                                              markerfacecolor="#bdbdbd", markeredgecolor="none",
                                              markersize=6, label=f"< {MIN_LETTURE} letture (dato insufficiente)")],
                              loc="lower right", frameon=True, facecolor="white", framealpha=0.9,
                              edgecolor="none", fontsize=9)
    ax.add_artist(legenda_dato)
    ax.legend(handles=proxy_dimensioni, title="dimensione = n. letture", title_fontsize=8.5,
              loc="lower right", bbox_to_anchor=(1, 0.155), frameon=True, facecolor="white",
              framealpha=0.9, edgecolor="none", fontsize=8.5)

    ultima_data = pd.to_datetime(sez["timestamp_utc"]).max().strftime("%d/%m %H:%M UTC")
    nota_bozza = " · preview, da confermare" if BOZZA else ""
    fig.text(0.01, 0.014, f"SEZ2011 {SEZ_ESEMPIO} · dati fino al {ultima_data}{nota_bozza}",
              fontsize=10, color=INK)

    # margine inferiore riservato esplicitamente (invece di tight_layout) cosi'
    # la didascalia sopra resta sotto la mappa senza sovrapporsi al credito
    # OpenStreetMap/CARTO che contextily disegna dentro l'angolo in basso a sinistra
    fig.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.055)
    nome_comune_file = comune.lower().replace(" ", "_").replace("'", "")
    out_path = CARTELLA_SCRIPT / f"mappa_reale_{nome_comune_file}.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    print(f"Salvato: {out_path}")


if __name__ == "__main__":
    main()
