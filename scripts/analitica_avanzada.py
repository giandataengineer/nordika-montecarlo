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


# 2. Intervalo de confianza sobre el uplift

def intervalo_uplift(
    delta_por_oportunidad: np.ndarray,
    n_replicas: int = 800,
    confianza: float = 0.90,
    semilla: int = 42,
) -> dict[str, float | str]:
    """Bootstrap sobre el delta contrafactual fila a fila.

    Importante para no vender mas de lo que hace: re-muestrea las predicciones ya
    calculadas, asi que mide **incertidumbre de muestreo** (¿cambiaria el delta con
    otra muestra de oportunidades?). No mide incertidumbre del modelo, que exigiria
    reentrenar en cada replica y cuesta unas 30 veces mas. El campo `alcance` lo
    deja escrito en el propio resultado.
    """
    datos = np.asarray(delta_por_oportunidad, dtype=float)
    datos = datos[np.isfinite(datos)]
    if datos.size == 0:
        return {"media": 0.0, "inferior": 0.0, "superior": 0.0, "alcance": "sin datos"}

    rng = np.random.default_rng(semilla)
    idx = rng.integers(0, datos.size, size=(n_replicas, datos.size))
    medias = datos[idx].mean(axis=1)

    cola = (1 - confianza) / 2
    inferior = float(np.percentile(medias, cola * 100))
    superior = float(np.percentile(medias, (1 - cola) * 100))
    media = float(datos.mean())

    return {
        "media": media,
        "inferior": inferior,
        "superior": superior,
        "amplitud": superior - inferior,
        "confianza": confianza,
        "replicas": n_replicas,
        # cruza el cero: el signo del efecto no esta asegurado
        "significativo": bool(inferior > 0 or superior < 0),
        "alcance": "incertidumbre de muestreo, no de modelo (no se reentrena por replica)",
    }


# 3. Estabilidad del ranking bajo re-muestreo

def estabilidad_ranking(
    simular: Callable[[int], pd.DataFrame],
    semillas: Iterable[int],
    columna_decision: str = "decision",
    columna_valor: str = "expected_profit_usd",
) -> dict[str, Any]:
    """Repite solo la capa Monte Carlo con distintas semillas y cuenta victorias.

    `simular(semilla)` debe devolver el resumen por decision de esa realizacion.
    Responde a "¿cuanto del ranking depende de los dados?", no a "¿cuanto depende
    de los datos?": para lo segundo habria que regenerar el dataset entero, que es
    un experimento distinto y mucho mas caro.
    """
    semillas = list(semillas)
    victorias: dict[str, int] = {}
    posiciones: dict[str, list[int]] = {}
    valores: dict[str, list[float]] = {}

    for s in semillas:
        resumen = simular(s).sort_values(columna_valor, ascending=False).reset_index(drop=True)
        for pos, fila in resumen.iterrows():
            nombre = str(fila[columna_decision])
            posiciones.setdefault(nombre, []).append(pos + 1)
            valores.setdefault(nombre, []).append(float(fila[columna_valor]))
        ganador = str(resumen.iloc[0][columna_decision])
        victorias[ganador] = victorias.get(ganador, 0) + 1

    total = len(semillas)
    detalle = []
    for nombre, pos in posiciones.items():
        vals = valores[nombre]
        detalle.append({
            "decision": nombre,
            "victorias": victorias.get(nombre, 0),
            "realizaciones": total,
            "tasa_victoria": victorias.get(nombre, 0) / total if total else 0.0,
            "posicion_media": float(np.mean(pos)),
            "posicion_peor": int(np.max(pos)),
            "beneficio_medio": float(np.mean(vals)),
            "beneficio_min": float(np.min(vals)),
            "beneficio_max": float(np.max(vals)),
        })
    detalle.sort(key=lambda d: d["tasa_victoria"], reverse=True)

    lider = detalle[0] if detalle else None
    return {
        "realizaciones": total,
        "semillas": semillas,
        "detalle": detalle,
        "ganador_estable": bool(lider and lider["tasa_victoria"] >= 0.80),
        "veredicto": (
            f"{lider['decision']} gana en {lider['victorias']} de {total} realizaciones"
            if lider else "sin datos"
        ),
        "alcance": "varia la semilla del Monte Carlo; el dataset y los modelos se mantienen fijos",
    }


# 4. Sensibilidad a la calibracion de los tres ruidos

def sensibilidad_ruidos(
    simular: Callable[[float, float, float], pd.DataFrame],
    factores: Sequence[float] = (0.5, 1.0, 1.5, 2.0),
    columna_decision: str = "decision",
    columna_valor: str = "expected_profit_usd",
) -> dict[str, Any]:
    """Escala cada ruido por separado y observa si el ranking aguanta.

    La magnitud de los tres ruidos la elige el analista. Sin esto es un numero
    puesto a mano dentro de una caja negra; con esto queda auditado: se ve a partir
    de que exageracion la conclusion cambia.
    """
    ruidos = ["incertidumbre", "ejecucion", "residual"]
    resultados = []
    ganador_base = None

    for i, ruido in enumerate(ruidos):
        fila = {"ruido": ruido, "puntos": []}
        for f in factores:
            escalas = [1.0, 1.0, 1.0]
            escalas[i] = f
            resumen = simular(*escalas).sort_values(columna_valor, ascending=False).reset_index(drop=True)
            ganador = str(resumen.iloc[0][columna_decision])
            if f == 1.0 and ganador_base is None:
                ganador_base = ganador
            fila["puntos"].append({
                "factor": f,
                "ganador": ganador,
                "beneficio_ganador": float(resumen.iloc[0][columna_valor]),
                "cambia": ganador_base is not None and ganador != ganador_base,
            })
        fila["punto_de_quiebre"] = next(
            (p["factor"] for p in fila["puntos"] if p["cambia"]), None
        )
        resultados.append(fila)

    frágiles = [r["ruido"] for r in resultados if r["punto_de_quiebre"] is not None]
    return {
        "ganador_base": ganador_base,
        "factores": list(factores),
        "resultados": resultados,
        "robusto": not frágiles,
        "veredicto": (
            "La recomendacion aguanta duplicar cualquiera de los tres ruidos"
            if not frágiles
            else "La recomendacion cambia al exagerar: " + ", ".join(frágiles)
        ),
    }


# 5. Valor esperado de la informacion perfecta

# TODO: revisar si el EVPI aguanta bien con mas de cuatro decisiones
def valor_informacion(matriz_escenarios: dict[str, np.ndarray]) -> dict[str, Any]:
    """EVPI: cuanto vale saber de antemano como va a salir el futuro.

    Con incertidumbre eliges la opcion de mayor media y te quedas con ella pase lo
    que pase. Con informacion perfecta elegirias, en cada escenario, la que mejor
    sale en ese escenario. La diferencia es el techo de lo que tiene sentido gastar
    en reducir incertidumbre: mas estudio, un piloto, mejores datos.

    `matriz_escenarios`: decision -> array de beneficios, todas con la misma longitud
    y el escenario i comparable entre decisiones.
    """
    nombres = list(matriz_escenarios.keys())
    if not nombres:
        return {"evpi": 0.0, "alcance": "sin datos"}

    matriz = np.vstack([np.asarray(matriz_escenarios[n], dtype=float) for n in nombres])
    medias = matriz.mean(axis=1)

    i_mejor = int(np.argmax(medias))
    sin_info = float(medias[i_mejor])
    con_info = float(matriz.max(axis=0).mean())
    evpi = con_info - sin_info

    # en cuantos escenarios la apuesta elegida NO era la mejor
    mejor_por_escenario = matriz.argmax(axis=0)
    acierto = float((mejor_por_escenario == i_mejor).mean())

    reparto = []
    for j, nombre in enumerate(nombres):
        cuota = float((mejor_por_escenario == j).mean())
        if cuota > 0:
            reparto.append({"decision": nombre, "cuota_escenarios": cuota})
    reparto.sort(key=lambda d: d["cuota_escenarios"], reverse=True)

    return {
        "decision_sin_informacion": nombres[i_mejor],
        "valor_sin_informacion": sin_info,
        "valor_con_informacion_perfecta": con_info,
        "evpi": evpi,
        "evpi_relativo": evpi / abs(sin_info) if sin_info else 0.0,
        "acierto_de_la_apuesta": acierto,
        "reparto_de_escenarios": reparto,
        "lectura": (
            f"Reducir la incertidumbre vale como maximo {evpi:,.0f} por decision. "
            f"La apuesta elegida es la mejor en el {acierto:.0%} de los escenarios."
        ),
    }


def _autocomprobacion() -> None:
    """Comprobaciones minimas: cada bloque falla si la logica se rompe."""
    ranking_malo = [
        {"decision": "Escalar paid social", "expected_profit_usd": 63446, "p10_usd": -33868, "probability_loss": 0.356},
        {"decision": "Optimizar la conversion del sitio", "expected_profit_usd": 53882, "p10_usd": 45485, "probability_loss": 0.0},
    ]
    informe = {"headline": "Es la opcion mas robusta por suelo positivo y perdida esperada practicamente nula.",
               "razones": ["El downside esta contenido.", "Beneficio de 63.446."]}
    res = coherencia_informe(informe, ranking_malo)
    assert res["frases_retiradas"] == 2, res
    # el titular se sustituye por una frase factual, no se queda vacio
    assert res["informe"]["headline"] == res["frase_sustituta"]
    assert "no se puede presentar como una apuesta de bajo riesgo" in res["informe"]["headline"]
    # los elementos de lista que fallan si se retiran
    assert res["informe"]["razones"] == ["Beneficio de 63.446."]

    ranking_bueno = [
        {"decision": "Optimizar la conversion del sitio", "expected_profit_usd": 66132, "p10_usd": 56068, "probability_loss": 0.0},
        {"decision": "Reactivacion y remarketing", "expected_profit_usd": 31154, "p10_usd": 20076, "probability_loss": 0.0},
    ]
    ok = coherencia_informe(informe, ranking_bueno)
    assert ok["frases_retiradas"] == 0, ok

    ci = intervalo_uplift(np.random.default_rng(1).normal(50, 10, 4000))
    assert ci["inferior"] < ci["media"] < ci["superior"]
    assert ci["significativo"] is True
    nulo = intervalo_uplift(np.random.default_rng(1).normal(0, 30, 4000))
    assert nulo["significativo"] is False

    rng = np.random.default_rng(0)
    evpi = valor_informacion({
        "A": rng.normal(100, 5, 5000),
        "B": rng.normal(95, 60, 5000),
    })
    assert evpi["evpi"] > 0
    assert 0 <= evpi["acierto_de_la_apuesta"] <= 1

    # una opcion que domina a la otra en todos los escenarios no deja valor a la informacion
    dominante = valor_informacion({"A": np.full(1000, 100.0), "B": np.full(1000, 10.0)})
    assert abs(dominante["evpi"]) < 1e-9, dominante

    print("analitica_avanzada: todas las comprobaciones pasan")


if __name__ == "__main__":
    _autocomprobacion()
