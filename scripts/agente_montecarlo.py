from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path: str | Path | None = None) -> bool:
        if dotenv_path is None:
            return False
        env_path = Path(dotenv_path)
        if not env_path.exists():
            return False
        loaded = False
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
                loaded = True
        return loaded

try:
    from .simulacion_montecarlo import (
        DATASET_PATH,
        LIVE_DASHBOARD_PATH,
        LIVE_STATUS_PATH,
        PARAMS_PATH,
        PROJECT_ROOT,
        ROOT,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
        run_pipeline,
    )
except ImportError:
    from simulacion_montecarlo import (
        DATASET_PATH,
        LIVE_DASHBOARD_PATH,
        LIVE_STATUS_PATH,
        PARAMS_PATH,
        PROJECT_ROOT,
        ROOT,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
        run_pipeline,
    )

load_dotenv(PROJECT_ROOT / ".env")

LIVE_DASHBOARD_RELATIVE_PATH = f"dashboards/{LIVE_DASHBOARD_PATH.name}"
LIVE_STATUS_RELATIVE_PATH = f"dashboards/{LIVE_STATUS_PATH.name}"

DECISION_ALIAS = {
    "conservadora": "Ventana conservadora",
    "regulacion": "Servicios de regulacion",
    "agresivo": "Arbitraje agresivo",
    "hibrido": "Hibrido certificado",
}

UPLIFT_ALIAS = {
    "control_fino": "control_fino_completo",
    "descarga_profunda": "descarga_profunda",
    "regulacion": "regulacion_convocada",
    "mercado_nuevo": "mercado_nuevo",
}

TOOL_PURPOSES = {
    "analizar_negocio": "Lee el historico de despacho y resume cobertura de degradacion, ingreso y margen neto por bloque horario.",
    "obtener_uplift_ml": "Consulta el uplift contrafactual estimado por el modelo para una palanca concreta.",
    "distribucion_montecarlo": "Lee la distribucion de 10.000 futuros de una decision para medir suelo, techo y riesgo.",
    "comparar_decisiones": "Ordena las alternativas lado a lado por beneficio esperado, ROI y probabilidad de perdida.",
    "ejecutar_simulacion_montecarlo": "Lanza una simulacion Monte Carlo nueva con dashboard live.",
    "estado_simulacion_montecarlo": "Consulta el progreso actual de la simulacion live.",
    "recargar_resultados_montecarlo": "Recarga el ranking consolidado tras una simulacion.",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe {path.name}. Ejecuta antes la simulacion.")
    return pd.read_csv(path)


def asegurar_outputs() -> None:
    required = [DATASET_PATH, PARAMS_PATH, SIMULATIONS_PATH, SUMMARY_PATH]
    if any(not path.exists() for path in required):
        run_pipeline(n_simulations=2000, live_dashboard=False, persist_outputs=True)


def cargar_artifacts() -> dict[str, pd.DataFrame]:
    asegurar_outputs()
    return {
        "dataset": _read_csv(DATASET_PATH),
        "parametros": _read_csv(PARAMS_PATH),
        "simulaciones": _read_csv(SIMULATIONS_PATH),
        "resumen": _read_csv(SUMMARY_PATH),
    }


def resumen_por_bloque(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Margen del historico agregado por bloque horario.

    Los nombres de columna salen del CSV que escribe el pipeline. Antes esta
    funcion pedia columnas en castellano que el generador nunca produjo, asi
    que reventaba con KeyError en cuanto el agente la invocaba.
    """
    if df is None:
        df = cargar_artifacts()["dataset"]
    resumen = (
        df.groupby("bloque_horario")
        .agg(
            ventanas=("ventana_id", "count"),
            cobertura=("cubrio_degradacion", "mean"),
            energia_mwh=("energia_mwh", "sum"),
            ingreso_usd=("ingreso_usd", "sum"),
            margen_neto_usd=("margen_neto_usd", "sum"),
            degradacion_media_usd=("coste_degradacion_usd", "mean"),
            diferencial_medio=("diferencial_usd_mwh", "mean"),
            indice_medio=("indice_despacho", "mean"),
        )
        .sort_values("margen_neto_usd", ascending=False)
    )
    return resumen


def resumen_ejecutivo(df_resumen: pd.DataFrame | None = None) -> pd.DataFrame:
    if df_resumen is None:
        df_resumen = cargar_artifacts()["resumen"]
    ejecutivo = df_resumen.rename(
        columns={
            "expected_profit_usd": "beneficio_esperado_usd",
            "probability_loss": "probabilidad_perdida",
            "expected_roi": "roi_esperado",
        }
    ).copy()
    for col in ("beneficio_esperado_usd", "p10_usd", "p50_usd", "p90_usd"):
        if col in ejecutivo.columns:
            ejecutivo[col] = ejecutivo[col].round(0).astype(int)
    if "probabilidad_perdida" in ejecutivo.columns:
        ejecutivo["probabilidad_perdida"] = (ejecutivo["probabilidad_perdida"] * 100).round(1)
    if "roi_esperado" in ejecutivo.columns:
        ejecutivo["roi_esperado"] = ejecutivo["roi_esperado"].round(2)
    return ejecutivo


def resumen_contrafactuales(df_parametros: pd.DataFrame | None = None) -> pd.DataFrame:
    if df_parametros is None:
        df_parametros = cargar_artifacts()["parametros"]
    columnas = [
        "parameter",
        "sample_size",
        "baseline_cobertura",
        "scenario_conversion",
        "uplift_conversion_pct",
        "profit_lift_per_window_usd",
        "source",
    ]
    disponibles = [col for col in columnas if col in df_parametros.columns]
    resumen = df_parametros[disponibles].copy()
    if "uplift_conversion_pct" in resumen.columns:
        resumen["uplift_conversion_pct"] = (resumen["uplift_conversion_pct"] * 100).round(1)
    if "profit_lift_per_window_usd" in resumen.columns:
        resumen["profit_lift_per_window_usd"] = resumen["profit_lift_per_window_usd"].round(2)
    return resumen


def ejecutar_simulacion_montecarlo(
    simulaciones_nuevas: int = 10000,
    modo: str = "background",
    progress_every: int = 100,
) -> dict[str, Any]:
    if modo not in {"background", "bloqueante"}:
        return {"error": "modo invalido", "opciones": ["background", "bloqueante"]}

    if modo == "bloqueante":
        result = run_pipeline(
            n_simulations=int(simulaciones_nuevas),
            live_dashboard=True,
            progress_every=int(progress_every),
            persist_outputs=True,
        )
        return {
            "status": "finalizado",
            "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
            "estado_path": LIVE_STATUS_RELATIVE_PATH,
            "top_decisiones": result["summary"].head(4).to_dict(orient="records"),
        }

    command = [
        sys.executable,
        str(ROOT / "simulacion_montecarlo.py"),
        "--simulations",
        str(int(simulaciones_nuevas)),
        "--live-dashboard",
        "--progress-every",
        str(int(progress_every)),
    ]
    process = subprocess.Popen(command, cwd=ROOT)
    return {
        "status": "lanzado",
        "pid": process.pid,
        "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
        "estado_path": LIVE_STATUS_RELATIVE_PATH,
    }


def estado_simulacion_montecarlo() -> dict[str, Any]:
    if not LIVE_STATUS_PATH.exists():
        return {
            "status": "sin_estado",
            "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
            "nota": "Todavia no existe el archivo de estado. Lanza antes la simulacion.",
        }
    return json.loads(LIVE_STATUS_PATH.read_text(encoding="utf-8"))


def recargar_resultados_montecarlo() -> dict[str, pd.DataFrame]:
    return cargar_artifacts()


def _tool_analizar_negocio(bloque: str = "todos") -> str:
    resumen = resumen_por_bloque().reset_index()
    if bloque == "todos":
        data = resumen.to_dict(orient="records")
    else:
        fila = resumen[resumen["bloque_horario"] == bloque]
        if fila.empty:
            return json.dumps(
                {"error": f"Bloque {bloque!r} no encontrado.", "disponibles": resumen["bloque_horario"].tolist()},
                ensure_ascii=False,
            )
        data = fila.iloc[0].to_dict()
    return json.dumps(data, ensure_ascii=False, default=float)


def _tool_obtener_uplift_ml(decision: str) -> str:
    clave = UPLIFT_ALIAS.get(decision.lower())
    if clave is None:
        return json.dumps({
            "error": f"{decision!r} no tiene uplift ML disponible.",
            "nota": "Para una estrategia completa usa directamente distribucion_montecarlo.",
            "opciones": list(UPLIFT_ALIAS.keys()),
        }, ensure_ascii=False)

    parametros = cargar_artifacts()["parametros"]
    fila = parametros[parametros["parameter"] == clave]
    if fila.empty:
        return json.dumps({"error": "Sin datos para esta decision."}, ensure_ascii=False)
    return json.dumps(fila.iloc[0].to_dict(), ensure_ascii=False, default=float)


def _tool_distribucion_montecarlo(decision: str) -> str:
    nombre = DECISION_ALIAS.get(decision.lower().replace(" ", "_"), decision)
    artifacts = cargar_artifacts()
    simulaciones = artifacts["simulaciones"]
    resumen = artifacts["resumen"]
    sim = simulaciones[simulaciones["decision"] == nombre]["incremental_profit_usd"]
    if sim.empty:
        return json.dumps({"error": "Decision no encontrada.", "disponibles": simulaciones["decision"].unique().tolist()}, ensure_ascii=False)
    fila = resumen[resumen["decision"] == nombre]
    stats = {
        "decision": nombre,
        "n_simulaciones": int(len(sim)),
        "beneficio_esperado_usd": round(float(sim.mean()), 2),
        "mediana_usd": round(float(sim.median()), 2),
        "p10_usd": round(float(sim.quantile(0.10)), 2),
        "p25_usd": round(float(sim.quantile(0.25)), 2),
        "p75_usd": round(float(sim.quantile(0.75)), 2),
        "p90_usd": round(float(sim.quantile(0.90)), 2),
        "probabilidad_perdida_pct": round(float((sim < 0).mean() * 100), 1),
        "roi_esperado": round(float(fila["expected_roi"].iloc[0]), 2) if not fila.empty else None,
        "volatilidad_std_usd": round(float(sim.std()), 2),
        "ratio_retorno_riesgo": round(float(sim.mean() / sim.std()), 4) if sim.std() > 0 else None,
    }
    return json.dumps(stats, ensure_ascii=False, default=float)


def _tool_comparar_decisiones() -> str:
    artifacts = cargar_artifacts()
    simulaciones = artifacts["simulaciones"]
    resumen = artifacts["resumen"]
    comparativa = []
    for decision in simulaciones["decision"].unique():
        sim = simulaciones[simulaciones["decision"] == decision]["incremental_profit_usd"]
        fila = resumen[resumen["decision"] == decision]
        comparativa.append(
            {
                "decision": decision,
                "beneficio_esperado_usd": round(float(sim.mean()), 0),
                "p10_usd": round(float(sim.quantile(0.10)), 0),
                "p90_usd": round(float(sim.quantile(0.90)), 0),
                "probabilidad_perdida_pct": round(float((sim < 0).mean() * 100), 1),
                "roi_esperado": round(float(fila["expected_roi"].iloc[0]), 2) if not fila.empty else None,
                "ratio_retorno_riesgo": round(float(sim.mean() / sim.std()), 4) if sim.std() > 0 else None,
            }
        )
    comparativa.sort(key=lambda row: row["beneficio_esperado_usd"], reverse=True)
    return json.dumps(comparativa, ensure_ascii=False, default=float)


def _tool_ejecutar_simulacion_montecarlo(
    simulaciones_nuevas: int = 10000,
    modo: str = "background",
    progress_every: int = 100,
) -> str:
    return json.dumps(
        ejecutar_simulacion_montecarlo(
            simulaciones_nuevas=simulaciones_nuevas,
            modo=modo,
            progress_every=progress_every,
        ),
        ensure_ascii=False,
        default=float,
    )


def _tool_estado_simulacion_montecarlo() -> str:
    return json.dumps(estado_simulacion_montecarlo(), ensure_ascii=False, default=float)


def _tool_recargar_resultados_montecarlo() -> str:
    artifacts = recargar_resultados_montecarlo()
    return json.dumps(
        {
            "status": "recargado",
            "n_filas_simulaciones": int(len(artifacts["simulaciones"])),
            "n_decisiones": int(artifacts["simulaciones"]["decision"].nunique()),
            "dashboard_path": str(LIVE_DASHBOARD_PATH),
        },
        ensure_ascii=False,
    )


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "analizar_negocio",
            "description": "Analiza el historico de despacho por bloque horario: cobertura de degradacion, energia movida, ingreso, margen neto y coste medio de degradacion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bloque": {"type": "string", "description": "Usa 'todos' para ver todos los bloques horarios."}
                },
                "required": ["bloque"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_uplift_ml",
            "description": "Devuelve el uplift contrafactual estimado para control_fino, descarga_profunda, regulacion o mercado_nuevo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["control_fino", "descarga_profunda", "regulacion", "mercado_nuevo"]}
                },
                "required": ["decision"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "distribucion_montecarlo",
            "description": "Devuelve la distribucion estadistica de la Monte Carlo para una decision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["conservadora", "regulacion", "agresivo", "hibrido"]}
                },
                "required": ["decision"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_decisiones",
            "description": "Compara todas las decisiones lado a lado con beneficio esperado y riesgo.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ejecutar_simulacion_montecarlo",
            "description": "Lanza una simulacion Monte Carlo nueva con dashboard vivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "simulaciones_nuevas": {"type": "integer"},
                    "modo": {"type": "string", "enum": ["background", "bloqueante"]},
                    "progress_every": {"type": "integer"},
                },
                "required": ["simulaciones_nuevas", "modo", "progress_every"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estado_simulacion_montecarlo",
            "description": "Lee el progreso actual del dashboard vivo.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recargar_resultados_montecarlo",
            "description": "Recarga los resultados generados por la ultima simulacion.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
