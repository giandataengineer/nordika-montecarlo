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
