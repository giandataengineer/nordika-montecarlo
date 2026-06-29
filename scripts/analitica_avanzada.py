"""Capas analiticas que el caso base no cubre.

Cinco bloques, cada uno responde a una pregunta que un revisor va a hacer:

- coherencia_informe   : el texto no puede contradecir a sus propias cifras.
- intervalo_uplift     : el delta del contrafactual con rango, no como punto seco.
- estabilidad_ranking  : cuanto del ranking es senal y cuanto es la realizacion.
- sensibilidad_ruidos  : que pasa si el analista se equivoco calibrando el ruido.
- valor_informacion    : cuanto vale reducir la incertidumbre antes de decidir.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd


# 1. Guardarrail de coherencia entre narrativa y numeros

# Cada regla es: (patron que aparece en el texto, condicion que lo haria falso,
# explicacion de por que se retira). El patron se busca sin acentos ni mayusculas.
_REGLAS: list[tuple[str, Callable[[dict[str, float]], bool], str]] = [
    (
        r"suelo positivo",
        lambda m: m["p10"] < 0,
        "el percentil 10 es negativo, asi que el suelo no es positivo",
    ),
    (
        r"perdida esperada practicamente nula|perdida esperada nula|sin riesgo de perdida",
        lambda m: m["prob_perdida"] > 0.05,
        "la probabilidad de perdida supera el 5%",
    ),
    (
        r"opcion mas robusta|mas robusta por suelo",
        lambda m: m["p10"] < 0 or m["prob_perdida"] > 0.10,
        "una opcion con suelo negativo o mas de 10% de perdida no puede llamarse la mas robusta",
    ),
    (
        r"downside esta contenido",
        lambda m: m["p10"] < 0 or m["prob_perdida"] > 0.10,
        "el downside no esta contenido con suelo negativo o perdida por encima del 10%",
    ),
    (
        r"retorno ajustado a control|mejor retorno ajustado",
        lambda m: m["prob_perdida"] > 0.20,
        "por encima del 20% de perdida no se puede presentar como retorno bajo control",
    ),
    (
        r"no depende de un empate estadistico|no depende de ruido marginal",
        lambda m: m["brecha_relativa"] < 0.10,
        "la ventaja sobre la segunda opcion es menor al 10%, asi que si podria ser un empate",
    ),
]

_ACENTOS = str.maketrans("áéíóúüñ", "aeiouun")


def _normaliza(texto: str) -> str:
    return texto.lower().translate(_ACENTOS)


def _metricas_ganador(ranking: Sequence[dict[str, Any]]) -> dict[str, float]:
    mejor = ranking[0]
    segundo = ranking[1] if len(ranking) > 1 else ranking[0]
    beneficio = float(mejor.get("expected_profit_usd", mejor.get("beneficio_esperado_usd", 0.0)))
    beneficio_2 = float(segundo.get("expected_profit_usd", segundo.get("beneficio_esperado_usd", 0.0)))
    perdida = float(mejor.get("probability_loss", mejor.get("probabilidad_perdida", 0.0)))
    # el payload del agente trae la probabilidad en porcentaje, el del pipeline en tanto por uno
    if perdida > 1.0:
        perdida = perdida / 100.0
    return {
        "p10": float(mejor.get("p10_usd", 0.0)),
        "prob_perdida": perdida,
        "brecha_relativa": (beneficio - beneficio_2) / abs(beneficio) if beneficio else 0.0,
    }


# Campos que no pueden quedarse vacios: si se retiran, se sustituyen por una
# frase construida solo con cifras verificadas.
_CAMPOS_OBLIGATORIOS = ("headline", "summary")


def _frase_factual(ranking: Sequence[dict[str, Any]], metricas: dict[str, float]) -> str:
    mejor = ranking[0]
    nombre = mejor.get("decision", "la opcion mejor situada")
    beneficio = float(mejor.get("expected_profit_usd", mejor.get("beneficio_esperado_usd", 0.0)))
    riesgo = (
        f"con un suelo (P10) de {metricas['p10']:,.0f} y {metricas['prob_perdida']:.1%} "
        "de probabilidad de perdida"
    )
    if metricas["p10"] < 0 or metricas["prob_perdida"] > 0.10:
        return (
            f"{nombre} lidera por beneficio esperado ({beneficio:,.0f}), pero {riesgo}: "
            "no se puede presentar como una apuesta de bajo riesgo."
        )
    return f"{nombre} lidera con {beneficio:,.0f} de beneficio esperado, {riesgo}."


def coherencia_informe(
    informe: dict[str, Any],
    ranking: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Revisa cada frase del informe contra las cifras del ranking.

    Los elementos de lista que fallan se retiran. Los campos obligatorios
    (titular y resumen) se sustituyen por una frase construida solo con cifras
    verificadas, porque dejarlos vacios rompe el informe. En los dos casos queda
    constancia en `incidencias`: el fallo del generador nunca se oculta.
    """
    metricas = _metricas_ganador(ranking)
    incidencias: list[dict[str, str]] = []
    sustituta = _frase_factual(ranking, metricas)

    def revisa(frase: str, ruta: str) -> bool:
        plano = _normaliza(frase)
        for patron, falla_si, motivo in _REGLAS:
            if re.search(patron, plano) and falla_si(metricas):
                incidencias.append({"ubicacion": ruta, "frase": frase, "motivo": motivo})
                return False
        return True

    def limpia(nodo: Any, ruta: str, clave: str = "") -> Any:
        if isinstance(nodo, str):
            if revisa(nodo, ruta):
                return nodo
            return sustituta if clave in _CAMPOS_OBLIGATORIOS else None
        if isinstance(nodo, list):
            return [v for v in (limpia(x, f"{ruta}[{i}]") for i, x in enumerate(nodo)) if v is not None]
        if isinstance(nodo, dict):
            return {k: limpia(v, f"{ruta}.{k}" if ruta else k, k) for k, v in nodo.items()}
        return nodo

    saneado = limpia(informe, "")
    return {
        "informe": saneado,
        "incidencias": incidencias,
        "frases_retiradas": len(incidencias),
        "frase_sustituta": sustituta,
        "metricas_contrastadas": metricas,
    }
