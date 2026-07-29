# -*- coding: utf-8 -*-
"""
Step 8 del progetto parallelo (vector tiles) - impatto di nuove colonnine sul
GAP score, per la sezione d'esempio usata nel resto della pipeline (Milano,
SEZ2011 151460002842, si veda 03-04-05-06).

Riproduce la metodologia del notebook di simulazione condiviso da un compagno
di gruppo (cartella Drive
8-Simulazione_Impatto_Nuove_Colonnine_Milano_GAP_Score,
Simulazione_Impatto_Nuove_Colonnine_Milano_GAP_Score.ipynb): GAP score = rango
percentile nazionale della domanda meno rango percentile nazionale
dell'offerta di colonnine; installare nuove colonnine entro 500m della
sezione sposta solo il suo rango di offerta, lasciando invariata la domanda.
Qui viene rieseguita solo per SEZ_ESEMPIO e solo per gli scenari 0-3 (non
0-7): per una slide interessa "quante ne servono per QUESTA sezione", non
l'andamento fino a 7.

Richiede due file che non fanno parte di questo repository (appartengono alla
pipeline del gap_score, cartella del progetto principale):
  - sezioni_gap_score_DEFINITIVO.parquet (universo nazionale eleggibile, con
    gap_score, offerta_colonnine_500m, distanza_colonnina_piu_vicina_m)
  - sezioni_critiche_milano.csv (le 817 sezioni critiche di Milano)

Output: grafico_gap_score_colonnine_milano.png
"""

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

CARTELLA_SCRIPT = Path(__file__).resolve().parent
# file della pipeline del gap_score, nel progetto principale (non in questo repository)
CARTELLA_PROGETTO_PRINCIPALE = Path(r"C:\Users\fasanelli michele\OneDrive\Desktop\Contesto lavoro di gruppo ETL")
IN_GAP_SCORE_NAZIONALE = CARTELLA_PROGETTO_PRINCIPALE / "sezioni_gap_score_DEFINITIVO.parquet"
IN_SEZIONI_CRITICHE_MILANO = CARTELLA_PROGETTO_PRINCIPALE / "sezioni_critiche_milano.csv"

SEZ_ESEMPIO = 151460002842  # stessa sezione di 03/04/05/06
SCENARI_NUOVE_COLONNINE = [0, 1, 2, 3]

INK = "#2b2b2b"
MUTED = "#5a5a5a"
ACCENT = "#c0392b"
GRID = "#e6e6e6"


def trova_gomito(y_ordinato):
    """Stessa implementazione di Ranking_Sezioni_Critiche_GAP_Score.ipynb /
    Ranking_Province_GAP_Score.ipynb: indice del punto di massima distanza
    dalla corda che unisce primo e ultimo punto della curva ordinata."""
    n = len(y_ordinato)
    x = np.arange(n, dtype=float)
    y = np.asarray(y_ordinato, dtype=float)
    x_n = (x - x.min()) / (x.max() - x.min())
    y_n = (y - y.min()) / (y.max() - y.min())
    x1, y1, x2, y2 = x_n[0], y_n[0], x_n[-1], y_n[-1]
    num = np.abs((y2 - y1) * x_n - (x2 - x1) * y_n + x2 * y1 - y2 * x1)
    den = np.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
    return int(np.argmax(num / den))


def costruisci_parametri_offerta(eleggibili_df):
    """Parametri di riferimento fissi (universo nazionale iniziale) per il
    ricalcolo di offerta_norm: i tre ingredienti di offerta_accessibilita()
    in gap_score_DEFINITIVO.ipynb."""
    servite = eleggibili_df["offerta_colonnine_500m"] > 0
    non_servite = ~servite
    return {
        "N": len(eleggibili_df),
        "Z": int(non_servite.sum()),
        "servite_sorted": np.sort(eleggibili_df.loc[servite, "offerta_colonnine_500m"].to_numpy()),
        "non_servite_negdist_sorted": np.sort(
            -eleggibili_df.loc[non_servite, "distanza_colonnina_piu_vicina_m"].to_numpy()),
    }


def _rango_medio(valori, riferimento_ordinato):
    """Rango medio (metodo 'average', identico a pandas.Series.rank()),
    vettorializzato con ricerca binaria."""
    valori = np.asarray(valori, dtype=float)
    sx = np.searchsorted(riferimento_ordinato, valori, side="left")
    dx = np.searchsorted(riferimento_ordinato, valori, side="right")
    return (sx + dx + 1) / 2.0


def offerta_norm_da_conteggio(conteggio, distanza, parametri):
    conteggio = np.asarray(conteggio, dtype=float)
    distanza = np.asarray(distanza, dtype=float)
    servita = conteggio > 0
    rango_servite = parametri["Z"] + _rango_medio(conteggio, parametri["servite_sorted"])
    rango_non_servite = _rango_medio(-np.nan_to_num(distanza, nan=0.0), parametri["non_servite_negdist_sorted"])
    rango = np.where(servita, rango_servite, rango_non_servite)
    return rango / parametri["N"]


def main():
    gap_nazionale = pd.read_parquet(
        IN_GAP_SCORE_NAZIONALE,
        columns=["SEZ2011", "gap_score", "offerta_colonnine_500m", "distanza_colonnina_piu_vicina_m"])
    eleggibili = gap_nazionale.dropna(subset=["gap_score"]).copy()

    critiche_ord = eleggibili[eleggibili["gap_score"] > 0].sort_values("gap_score", ascending=False)
    soglia_critica = float(critiche_ord["gap_score"].to_numpy()[trova_gomito(critiche_ord["gap_score"].to_numpy())])

    milano = pd.read_csv(IN_SEZIONI_CRITICHE_MILANO)
    milano = milano.merge(
        gap_nazionale[["SEZ2011", "offerta_colonnine_500m", "distanza_colonnina_piu_vicina_m"]],
        on="SEZ2011", how="left")
    sezione = milano[milano["SEZ2011"] == SEZ_ESEMPIO]
    if sezione.empty:
        raise ValueError(f"SEZ2011={SEZ_ESEMPIO} non trovata fra le sezioni critiche di Milano")
    sezione = sezione.iloc[0]
    comune = sezione["COMUNE"]

    parametri = costruisci_parametri_offerta(eleggibili)
    offerta_norm_iniziale = offerta_norm_da_conteggio(
        [sezione["offerta_colonnine_500m"]], [sezione["distanza_colonnina_piu_vicina_m"]], parametri)[0]
    domanda_norm = sezione["gap_score"] + offerta_norm_iniziale

    risultati = []
    for n_nuove in SCENARI_NUOVE_COLONNINE:
        colonnine_simulate = sezione["offerta_colonnine_500m"] + n_nuove
        offerta_norm_sim = offerta_norm_da_conteggio(
            [colonnine_simulate], [sezione["distanza_colonnina_piu_vicina_m"]], parametri)[0]
        risultati.append({"nuove_colonnine": n_nuove, "gap_score": domanda_norm - offerta_norm_sim})
    scenari = pd.DataFrame(risultati)

    scarto = abs(scenari.loc[scenari["nuove_colonnine"] == 0, "gap_score"].iloc[0] - sezione["gap_score"])
    assert scarto < 1e-6, f"Scenario 0 non riproduce il gap_score originale (scarto {scarto:.2e})"

    # ------------------------------------------------------------ figura
    cmap = plt.get_cmap("YlOrRd")
    vmax = float(np.ceil(scenari["gap_score"].max() * 20) / 20)  # arrotonda per eccesso al 0.05
    norm = Normalize(vmin=0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=200)

    colori = [cmap(norm(v)) for v in scenari["gap_score"]]
    barre = ax.bar(scenari["nuove_colonnine"], scenari["gap_score"], color=colori,
                    edgecolor="white", linewidth=1.2, width=0.62, zorder=3)

    # etichetta del valore SEMPRE sopra la barra (mai dentro/sotto): tenerla in una
    # posizione unica ed esterna alla barra evita che si scontri sia con la linea
    # della soglia sia con la freccia dell'annotazione "sotto soglia" qui sotto
    for barra, valore in zip(barre, scenari["gap_score"]):
        ax.annotate(f"{valore:.3f}", (barra.get_x() + barra.get_width() / 2, valore),
                    xytext=(0, 6), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")

    ax.axhline(soglia_critica, color=ACCENT, linestyle=(0, (5, 3)), linewidth=1.6, zorder=2)
    # etichetta della soglia ancorata al bordo sinistro del grafico (x in coordinate
    # axes-fraction, y in coordinate dati): resta sempre nello spazio vuoto fra le
    # barre 0 e 1, indipendentemente da dove cadono le etichette dei valori
    ax.text(0.015, soglia_critica, f"soglia critica (gomito) = {soglia_critica:.3f}",
            transform=ax.get_yaxis_transform(), ha="left", va="bottom",
            fontsize=9.5, color=ACCENT, fontweight="bold",
            path_effects=[pe.withStroke(linewidth=2.5, foreground="white")])

    idx_sotto_soglia = next((i for i, v in enumerate(scenari["gap_score"]) if v < soglia_critica), None)

    ax.set_xticks(scenari["nuove_colonnine"])
    ax.set_xlabel("nuove colonnine installate entro 500 m", fontsize=10, color=MUTED)
    ax.set_ylabel("GAP score", fontsize=10, color=MUTED)
    ax.set_ylim(0, max(vmax, soglia_critica) * 1.12)
    ax.set_title(f"Impatto di nuove colonnine sul GAP score — {comune}",
                 fontsize=14, color=INK, loc="left", pad="14", fontweight="bold")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=MUTED)

    # l'etichetta dell'asse x della barra che scende sotto soglia si distingue in
    # rosso e grassetto (invece di un'altra freccia, che a questa densita' di
    # annotazioni finirebbe per sovrapporsi a qualcos'altro)
    if idx_sotto_soglia is not None:
        n_sotto = int(scenari["nuove_colonnine"].iloc[idx_sotto_soglia])
        for etichetta in ax.get_xticklabels():
            if etichetta.get_text() == str(n_sotto):
                etichetta.set_color(ACCENT)
                etichetta.set_fontweight("bold")

    nota_soglia = (f" · scende sotto soglia con {n_sotto} nuove colonnin{'a' if n_sotto == 1 else 'e'}"
                   if idx_sotto_soglia is not None else "")
    fig.text(0.01, 0.01,
              f"SEZ2011 {SEZ_ESEMPIO} ({comune}) · simulazione: solo la componente di offerta "
              f"cambia, la domanda resta invariata{nota_soglia}",
              fontsize=7.6, color=MUTED)

    plt.tight_layout(rect=(0, 0.035, 1, 1))
    nome_comune_file = comune.lower().replace(" ", "_").replace("'", "")
    out_path = CARTELLA_SCRIPT / f"grafico_gap_score_colonnine_{nome_comune_file}.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    print(f"Salvato: {out_path}")
    print(scenari.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
