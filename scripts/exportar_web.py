"""Exporta a JSON todo lo que la consola necesita para correr sin backend.

Los modelos de ML se entrenan aqui, en Python, como siempre. Lo que se exporta
es el resultado: el valor esperado de cada oportunidad bajo el escenario base y
bajo cada estrategia. Con eso el navegador puede hacer el remuestreo y los
tres ruidos por su cuenta, que es aritmetica y le sobra.

Asi la pagina desplegada no necesita servidor: ni cold start, ni rate limit,
ni una simulacion de 40 segundos ida y vuelta.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from simulacion_montecarlo import (
    NOISE_PROFILES,
    SEED,
    build_aov_model,
    build_conversion_model,
    generate_dataset,
    predict_components,
    scenario_frames,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SALIDA = PROJECT_ROOT / "web" / "public" / "motor.json"
SALIDA_PAYLOAD = PROJECT_ROOT / "web" / "public" / "payload.json"


def exportar(destino: Path = SALIDA) -> Path:
    df = generate_dataset()
    modelo_cobertura, auc = build_conversion_model(df)
    modelo_valor = build_aov_model(df)

    rng = np.random.default_rng(SEED)
    recientes = df[df["date"] >= "2025-10-01"].copy()
    if len(recientes) < 2500:
        recientes = df.tail(4500).copy()
    base = recientes.sample(min(3600, len(recientes)), replace=True, random_state=SEED)
    base = base.reset_index(drop=True)

    p0, a0, m0, c0 = predict_components(base, modelo_cobertura, modelo_valor)
    valor_base = p0 * a0 * m0 - c0 - p0 * 22

    estrategias = {}
    for decision, (frame, coste_fijo) in scenario_frames(base, rng).items():
        p, a, m, c = predict_components(frame, modelo_cobertura, modelo_valor)
        valor = p * a * m - c - p * 22
        perfil = NOISE_PROFILES.get(decision, NOISE_PROFILES["_default"])
        estrategias[decision] = {
            "valor": [round(float(v), 3) for v in valor],
            "coste_fijo": float(coste_fijo),
            # mismo tamano que la base significa comparacion 1 a 1; distinto
            # significa que la estrategia anade oportunidades nuevas
            "mismo_tamano": len(valor) == len(valor_base),
            "ruido": {
                "incertidumbre": list(perfil["uncertainty"]),
                "ejecucion": [list(perfil["execution"][0]), list(perfil["execution"][1])],
                "residual": list(perfil["residual"]),
            },
        }

    salida = {
        "semilla": SEED,
        "auc": round(float(auc), 4),
        "valor_base": [round(float(v), 3) for v in valor_base],
        "estrategias": estrategias,
    }

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, separators=(",", ":")), encoding="utf-8")
    return destino


def exportar_payload(destino: Path = SALIDA_PAYLOAD) -> Path:
    """El resto de la consola: dataset, modelos, uplift, informe y lecturas.

    Es lo mismo que servia /api/payload, pero congelado en un archivo. La
    pagina desplegada no necesita backend para nada.
    """
    from dashboard_agente_demo import _build_payload

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(_build_payload(), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return destino


if __name__ == "__main__":
    for ruta in (exportar(), exportar_payload()):
        print(f"escrito: {ruta.name}  ({ruta.stat().st_size / 1024:.0f} KB)")
