from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATA_DIR = PROJECT_ROOT / "datos"
DASHBOARDS_DIR = PROJECT_ROOT / "dashboards"
DATASET_PATH = DATA_DIR / "dataset_ventas_transaccional_sintetico_es.csv"
PARAMS_PATH = DATA_DIR / "parametros_estimados_desde_historico.csv"
SIMULATIONS_PATH = DATA_DIR / "resultados_simulacion_10000.csv"
SUMMARY_PATH = DATA_DIR / "resumen_simulacion.csv"
REPORT_PATH = DATA_DIR / "evaluacion_dataset.md"
LIVE_DASHBOARD_PATH = DASHBOARDS_DIR / "dashboard_live_montecarlo.html"
LIVE_STATUS_PATH = DASHBOARDS_DIR / "estado_live_montecarlo.json"
LIVE_STATUS_SCRIPT_PATH = DASHBOARDS_DIR / "estado_live_montecarlo.js"
LIVE_DASHBOARD_RELATIVE_PATH = f"dashboards/{LIVE_DASHBOARD_PATH.name}"
DEBUG_LOG_PATH = DATA_DIR / "mission_control_debug.log"

SEED = 42
N_ROWS = 20_000
N_SIMULATIONS = 10_000


def _debug_log(event: str, **fields: object) -> None:
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "simulacion_montecarlo",
            "event": event,
            **fields,
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _should_log_live_update(current_simulation: int, total_simulations: int) -> bool:
    if total_simulations <= 0:
        return True
    if current_simulation in {0, total_simulations}:
        return True
    checkpoint = max(1, total_simulations // 10)
    return current_simulation % checkpoint == 0


# ---------------------------------------------------------------------------
# Dominio: operacion de una bateria de red (BESS) de 20 MW / 80 MWh.
# Cada fila es una VENTANA DE DESPACHO de una hora: el precio que habia, el
# estado de carga con el que se llego, que palancas de operacion estaban
# activas y si el ciclo llego a cubrir su propio coste de degradacion.
# ---------------------------------------------------------------------------

# Bloques horarios. El precio spot no se comporta igual a las 3 de la mañana
# que en la punta de la tarde, y esa diferencia es de donde sale el margen.
BLOQUES_HORARIOS = [
    "madrugada",
    "manana",
    "valle_solar",
    "punta_tarde",
    "punta_noche",
    "noche",
]

# Nodo de la red donde inyecta. La congestion local cambia el precio.
ZONAS = ["Nodo Sur", "Nodo Centro", "Nodo Norte", "Nodo Costa", "Nodo Sierra"]

# Estado del sistema en esa hora, marcado por el operador de red.
ESTADOS_RED = ["holgado", "normal", "ajustado", "critico"]

# Producto al que se destina esa ventana.
PRODUCTOS = ["arbitraje", "regulacion", "reserva", "ocioso"]

TIPOS_DIA = ["laborable", "sabado", "domingo_festivo"]


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1 / (1 + np.exp(-x))


def choose(rng: np.random.Generator, values: list[str], probs: list[float]) -> str:
    return str(rng.choice(values, p=np.array(probs) / np.sum(probs)))


def bloque_horario(hora: int) -> str:
    """Los seis bloques siguen la curva de demanda diaria."""
    if hora < 6:
        return "madrugada"
    if hora < 11:
        return "manana"
    if hora < 16:
        return "valle_solar"
    if hora < 20:
        return "punta_tarde"
    if hora < 23:
        return "punta_noche"
    return "noche"


def presion_del_sistema(date: pd.Timestamp) -> str:
    """Periodos de tension del sistema, analogos a la estacionalidad real.

    El estiaje y las puntas de verano aprietan la oferta y ensanchan los
    diferenciales de precio; los meses de hidrologia abundante los estrechan.
    """
    ym = date.year * 100 + date.month
    if ym <= 202403:
        return "holgado"
    if ym <= 202408:
        return "ajustado"
    if ym <= 202412:
        return "normal"
    if ym <= 202503:
        return "holgado"
    if ym <= 202506:
        return "critico"
    if ym <= 202509:
        return "normal"
    if ym <= 202512:
        return "ajustado"
    if ym <= 202602:
        return "critico"
    return "normal"


def generate_dates(rng: np.random.Generator) -> pd.DatetimeIndex:
    """Ventanas horarias sobre el horizonte, con mas peso donde hay mas actividad.

    No se muestrea el calendario completo hora a hora: la bateria no opera las
    24 horas, solo las ventanas en las que hubo decision de despacho.
    """
    horas = pd.date_range("2024-01-01", "2026-04-30 23:00", freq="h")
    t = np.arange(len(horas))
    tendencia = 1 + 0.0009 * (t / 24)
    estacional = 1 + 0.10 * np.sin(2 * np.pi * (horas.dayofyear.to_numpy() / 365.25))
    # las horas de punta concentran la operacion
    hora_del_dia = horas.hour.to_numpy()
    perfil = np.where((hora_del_dia >= 16) & (hora_del_dia < 23), 1.9, 1.0)
    perfil = np.where((hora_del_dia >= 11) & (hora_del_dia < 16), 1.45, perfil)
    pesos = tendencia * estacional * perfil
    pesos = pesos / pesos.sum()
    return pd.DatetimeIndex(rng.choice(horas, size=N_ROWS, replace=True, p=pesos)).sort_values()


def generate_dataset() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = generate_dates(rng)
    rows = []

    # Los ciclos consumidos se acumulan a lo largo del horizonte: es lo que
    # convierte el desgaste en un coste creciente y no en una constante.
    ciclos_acumulados = 0.0

    for idx, date in enumerate(dates, start=1):
        month_index = (date.year - 2024) * 12 + date.month - 1
        quarter = f"{date.year}Q{((date.month - 1) // 3) + 1}"
        hora = int(date.hour)
        bloque = bloque_horario(hora)

        if date.dayofweek == 5:
            tipo_dia = "sabado"
        elif date.dayofweek == 6:
            tipo_dia = "domingo_festivo"
        else:
            tipo_dia = "laborable"

        estado_red = presion_del_sistema(date)
        zona = choose(rng, ZONAS, [0.30, 0.24, 0.18, 0.16, 0.12])

        # --- precio spot -------------------------------------------------
        # Base por bloque horario: el valle solar hunde el precio y la punta
        # de la tarde lo dispara. Es la curva que hace posible el arbitraje.
        base_precio = {
            "madrugada": 34.0,
            "manana": 52.0,
            "valle_solar": 26.0,
            "punta_tarde": 88.0,
            "punta_noche": 96.0,
            "noche": 48.0,
        }[bloque]

        factor_estado = {"holgado": 0.82, "normal": 1.0, "ajustado": 1.24, "critico": 1.62}[estado_red]
        factor_dia = {"laborable": 1.0, "sabado": 0.88, "domingo_festivo": 0.79}[tipo_dia]
        factor_zona = {
            "Nodo Sur": 1.00,
            "Nodo Centro": 1.06,
            "Nodo Norte": 0.94,
            "Nodo Costa": 1.09,
            "Nodo Sierra": 0.91,
        }[zona]

        # Lognormal: los precios de electricidad tienen cola derecha gruesa.
        # La mayoria de las horas son planas y unas pocas se disparan.
        mu = np.log(base_precio * factor_estado * factor_dia * factor_zona)
        precio_spot = float(np.clip(rng.lognormal(mu, 0.34), 4.0, 620.0))

        # El diferencial es lo que separa esta hora del valle del mismo dia.
        precio_valle = float(np.clip(rng.lognormal(np.log(24.0 * factor_estado), 0.28), 2.0, 120.0))
        diferencial = round(max(0.0, precio_spot - precio_valle), 2)

        # --- estado del activo -------------------------------------------
        soc_inicial = float(np.clip(rng.normal(62, 19), 8, 100))

        # --- palancas de operacion ---------------------------------------
        # Cada una entra en produccion en una fecha distinta, igual que en una
        # instalacion real: primero se opera a mano y luego se automatiza.
        if date < pd.Timestamp("2024-09-15"):
            profundidad_descarga = "conservadora"
        elif date < pd.Timestamp("2025-01-01"):
            profundidad_descarga = choose(rng, ["conservadora", "profunda"], [0.58, 0.42])
        else:
            profundidad_descarga = choose(rng, ["conservadora", "profunda"], [0.30, 0.70])

        if date < pd.Timestamp("2025-03-15"):
            ventana_carga = "estandar"
        elif date < pd.Timestamp("2025-07-01"):
            ventana_carga = choose(rng, ["estandar", "optimizada"], [0.52, 0.48])
        else:
            ventana_carga = choose(rng, ["estandar", "optimizada"], [0.28, 0.72])

        # Reserva de capacidad comprometida con el operador.
        if date < pd.Timestamp("2025-03-15"):
            reserva_comprometida = 0
        elif date < pd.Timestamp("2025-07-01"):
            reserva_comprometida = int(rng.random() < 0.42)
        else:
            reserva_comprometida = int(rng.random() < 0.76)

        # Control de rampa: suaviza la transicion y reduce el desgaste.
        if date < pd.Timestamp("2025-08-01"):
            rampa_optimizada = 0
        else:
            rampa_optimizada = int(rng.random() < 0.64)

        # Regulacion de frecuencia: se oferta y no siempre se convoca. Ese
        # hueco entre ofertar y ser llamado es el riesgo de ejecucion real.
        hora_apta = bloque in {"punta_tarde", "punta_noche", "manana"}
        regulacion_ofertada = int(
            date >= pd.Timestamp("2025-01-10") and hora_apta and rng.random() < 0.27
        )
        prob_convocatoria = 0.17
        prob_convocatoria += 0.14 if estado_red in {"ajustado", "critico"} else 0
        prob_convocatoria += 0.07 if tipo_dia == "laborable" else 0
        prob_convocatoria += 0.05 if zona in {"Nodo Centro", "Nodo Costa"} else 0
        regulacion_convocada = int(
            regulacion_ofertada and rng.random() < min(prob_convocatoria, 0.55)
        )

        # Mercado nuevo: solo en nodos con habilitacion tramitada.
        zona_habilitada = zona in {"Nodo Centro", "Nodo Costa", "Nodo Sur"}
        if date < pd.Timestamp("2025-10-01"):
            mercado_nuevo = 0
        elif date < pd.Timestamp("2026-01-15"):
            mercado_nuevo = int(zona_habilitada and rng.random() < 0.18)
        else:
            mercado_nuevo = int(zona_habilitada and rng.random() < 0.12)

        producto = "regulacion" if regulacion_convocada else (
            "reserva" if reserva_comprometida and diferencial < 18 else (
                "arbitraje" if diferencial >= 12 else "ocioso"
            )
        )

        # --- atractivo de la ventana -------------------------------------
        # Puntuacion 1-99 que resume si merecia la pena despachar aqui.
        calidad_bloque = {
            "punta_noche": 14,
            "punta_tarde": 12,
            "manana": 8,
            "noche": 5,
            "madrugada": 1,
            "valle_solar": -4,
        }[bloque]
        calidad_estado = {"critico": 8, "ajustado": 6, "normal": 0, "holgado": -3}[estado_red]
        calidad_soc = 12 if soc_inicial > 70 else (5 if soc_inicial > 40 else -6)
        calidad_desgaste = -15 if ciclos_acumulados > 900 else (-6 if ciclos_acumulados > 500 else 3)
        puntuacion = (
            52
            + calidad_bloque
            + calidad_estado
            + calidad_soc
            + calidad_desgaste
            + rng.normal(0, 11)
        )
        indice_despacho = int(np.clip(round(puntuacion), 1, 99))

        # --- energia movida y coste de degradacion -----------------------
        energia_base = {
            "conservadora": 3.2,
            "profunda": 7.0,
        }[profundidad_descarga]
        energia_mwh = float(
            np.clip(rng.lognormal(np.log(energia_base), 0.21), 0.8, 40.0)
        )
        energia_mwh = round(min(energia_mwh, soc_inicial / 100 * 80.0), 2)

        # El desgaste crece MAS que proporcionalmente con la profundidad de
        # descarga: ese exponente es el corazon del caso. Duplicar la energia
        # movida no duplica el coste, lo multiplica por mas de dos.
        exponente_desgaste = 2.00 if profundidad_descarga == "profunda" else 1.05
        coste_unitario = 13.5 * (1 + ciclos_acumulados / 2600.0)
        coste_unitario *= 0.88 if rampa_optimizada else 1.0
        coste_degradacion = float(
            rng.lognormal(
                np.log(coste_unitario * (energia_mwh / 4.0) ** exponente_desgaste), 0.19
            )
        )
        coste_degradacion = round(max(0.4, coste_degradacion), 2)

        # Solo las ventanas que realmente despachan consumen vida util.
        # Contar tambien las horas ociosas inflaba el desgaste cinco veces.
        ciclos_equivalentes = round(energia_mwh / 80.0, 4) if producto != "ocioso" else 0.0
        ciclos_acumulados += ciclos_equivalentes

        # --- objetivo: el ciclo cubrio su propio coste de degradacion ----
        logit = -3.00
        logit += (indice_despacho - 50) * 0.032
        logit += {
            "punta_noche": 0.46,
            "punta_tarde": 0.34,
            "manana": 0.16,
            "noche": 0.08,
            "madrugada": -0.08,
            "valle_solar": -0.16,
        }[bloque]
        logit += {"critico": 0.12, "ajustado": 0.08, "normal": 0.0, "holgado": -0.10}[estado_red]
        logit += {"laborable": 0.22, "sabado": -0.04, "domingo_festivo": -0.16}[tipo_dia]
        logit += {
            "Nodo Costa": 0.16,
            "Nodo Centro": 0.22,
            "Nodo Sur": 0.03,
            "Nodo Norte": -0.04,
            "Nodo Sierra": -0.18,
        }[zona]
        logit += 0.19 if ventana_carga == "optimizada" else 0
        logit += 0.18 if rampa_optimizada else 0
        logit += 0.21 if reserva_comprometida else 0
        logit += 0.48 if regulacion_convocada else (0.04 if regulacion_ofertada else 0)
        # Descargar profundo mueve mas energia pero encarece el ciclo: en
        # muchas ventanas el margen no llega a cubrir el desgaste extra.
        logit += -0.28 if profundidad_descarga == "profunda" else 0.06
        logit += 0.0032 * diferencial
        logit += -0.22 if mercado_nuevo else 0
        logit += -0.00045 * ciclos_acumulados
        logit += 0.004 * month_index
        prob_cobertura = float(np.clip(sigmoid(logit), 0.005, 0.58))
        cubrio_degradacion = int(rng.random() < prob_cobertura)

        # --- ingreso del ciclo -------------------------------------------
        precio_captado = diferencial
        if ventana_carga == "optimizada":
            precio_captado *= 1.09
        if regulacion_convocada:
            precio_captado *= 1.12
        if mercado_nuevo:
            precio_captado *= 2.35
        precio_captado = round(float(np.clip(precio_captado, 0.5, 480.0)), 2)

        ingreso = round(cubrio_degradacion * energia_mwh * precio_captado, 2)

        margen_base = 0.73
        margen_base += {
            "punta_noche": 0.04,
            "punta_tarde": 0.03,
            "manana": 0.02,
            "noche": 0.03,
            "madrugada": -0.01,
            "valle_solar": -0.04,
        }[bloque]
        margen_base += -0.030 if mercado_nuevo else 0
        margen_operativo = round(float(np.clip(rng.normal(margen_base, 0.035), 0.52, 0.86)), 3)

        coste_operativo = 22 if cubrio_degradacion else 0
        margen_bruto = round(ingreso * margen_operativo, 2)
        margen_neto = round(margen_bruto - coste_degradacion - coste_operativo, 2)

        latencia_respuesta = (
            int(max(0, rng.gamma(2.0, 3.0) - (2 if rampa_optimizada else 0)))
            if cubrio_degradacion
            else ""
        )

        rows.append(
            {
                "ventana_id": f"VD-{idx:06d}",
                "date": date.date().isoformat(),
                "hora": hora,
                "month": date.strftime("%Y-%m"),
                "quarter": quarter,
                "bloque_horario": bloque,
                "producto_despacho": producto,
                "tipo_dia": tipo_dia,
                "estado_red": estado_red,
                "zona_red": zona,
                "profundidad_descarga": profundidad_descarga,
                "ventana_carga": ventana_carga,
                "precio_spot_usd_mwh": round(precio_spot, 2),
                "diferencial_usd_mwh": diferencial,
                "soc_inicial_pct": round(soc_inicial, 1),
                "reserva_comprometida": reserva_comprometida,
                "rampa_optimizada": rampa_optimizada,
                "regulacion_ofertada": regulacion_ofertada,
                "regulacion_convocada": regulacion_convocada,
                "mercado_nuevo": mercado_nuevo,
                "indice_despacho": indice_despacho,
                "ciclos_acumulados": round(ciclos_acumulados, 3),
                "coste_degradacion_usd": coste_degradacion,
                "cubrio_degradacion": cubrio_degradacion,
                "latencia_respuesta_min": latencia_respuesta,
                "energia_mwh": energia_mwh if cubrio_degradacion else 0.0,
                "ingreso_usd": ingreso,
                "margen_operativo_pct": margen_operativo,
                "margen_bruto_usd": margen_bruto,
                "margen_neto_usd": margen_neto,
            }
        )

    return pd.DataFrame(rows)


CATEGORICAL = [
    "bloque_horario",
    "producto_despacho",
    "tipo_dia",
    "estado_red",
    "zona_red",
    "profundidad_descarga",
    "ventana_carga",
]

NUMERIC = [
    "precio_spot_usd_mwh",
    "diferencial_usd_mwh",
    "soc_inicial_pct",
    "coste_degradacion_usd",
    "reserva_comprometida",
    "rampa_optimizada",
    "regulacion_ofertada",
    "regulacion_convocada",
    "mercado_nuevo",
    "indice_despacho",
    "ciclos_acumulados",
]

FEATURES = CATEGORICAL + NUMERIC
