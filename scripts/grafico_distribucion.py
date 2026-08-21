"""Genera el grafico de la distribucion de los 10.000 escenarios.

Es la imagen que cuenta el caso sin texto: la conservadora entera a la derecha
del cero, la agresiva casi entera a la izquierda. Se usa en el README y en el
post.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIMULACIONES = PROJECT_ROOT / "datos" / "resultados_simulacion_10000.csv"
SALIDA = PROJECT_ROOT / "datos" / "distribucion_escenarios.png"

COLORES = {
    "Ventana conservadora": "#158a5c",
    "Servicios de regulacion": "#2f80ed",
    "Arbitraje agresivo": "#d9531e",
    "Hibrido certificado": "#7c3aed",
}


def dibujar(destino: Path = SALIDA) -> Path:
    sim = pd.read_csv(SIMULACIONES)
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=160)
    fig.patch.set_facecolor("#ededed")
    ax.set_facecolor("#ededed")

    # El hibrido tiene una cola hasta 2.900k que aplasta al resto. Se recorta
    # el eje al rango donde vive el 99 % de los escenarios y se avisa del corte.
    todos = sim["incremental_profit_usd"] / 1000
    izq, der = todos.quantile(0.005), todos.quantile(0.985)

    orden = (
        sim.groupby("decision")["incremental_profit_usd"].mean().sort_values(ascending=False).index
    )
    bins = np.linspace(izq, der, 60)
    for decision in orden:
        datos = (sim[sim.decision == decision]["incremental_profit_usd"] / 1000).clip(izq, der)
        ax.hist(
            datos,
            bins=bins,
            alpha=0.75,
            label=decision,
            color=COLORES.get(decision, "#666"),
            edgecolor="none",
        )
    ax.set_xlim(izq, der)

    ax.axvline(0, color="#131313", linewidth=1.4, zorder=5)
    tope = ax.get_ylim()[1]
    # las etiquetas van pegadas al eje, no arriba, para no chocar con la leyenda
    ax.text(-4, tope * 0.055, "pierde dinero", fontsize=11, color="#b8420f",
            ha="right", weight="bold")
    ax.text(4, tope * 0.055, "gana dinero", fontsize=11, color="#117a50",
            ha="left", weight="bold")

    ax.set_xlabel("Resultado del ano, en miles de dolares", fontsize=11, color="#131313")
    ax.set_ylabel("Escenarios", fontsize=11, color="#131313")
    ax.set_title(
        "10.000 futuros simulados por estrategia de operacion",
        fontsize=16, color="#131313", pad=16, loc="left", weight="bold",
    )

    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c9c8c6")
    ax.tick_params(colors="#565656")
    ax.grid(axis="y", color="#dedddc", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10.5, loc="upper left", bbox_to_anchor=(0.015, 0.99))

    # el hibrido se sale del grafico por la derecha, conviene decirlo
    ax.text(
        0.99, -0.13,
        "Hibrido certificado tiene una cola hasta 2.891k que queda fuera del recorte",
        transform=ax.transAxes, ha="right", fontsize=8.5, color="#828282",
    )

    fig.tight_layout()
    fig.savefig(destino, facecolor=fig.get_facecolor())
    plt.close(fig)
    return destino


if __name__ == "__main__":
    ruta = dibujar()
    sim = pd.read_csv(SIMULACIONES)
    print(f"escrito: {ruta}")
    for d, g in sim.groupby("decision"):
        v = g["incremental_profit_usd"]
        print(f"  {d:26s} negativos: {(v < 0).sum():5,} de {len(v):,}")
