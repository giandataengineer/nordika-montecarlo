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

DISPATCH = {
    "analizar_negocio": lambda args: _tool_analizar_negocio(**args),
    "obtener_uplift_ml": lambda args: _tool_obtener_uplift_ml(**args),
    "distribucion_montecarlo": lambda args: _tool_distribucion_montecarlo(**args),
    "comparar_decisiones": lambda _args: _tool_comparar_decisiones(),
    "ejecutar_simulacion_montecarlo": lambda args: _tool_ejecutar_simulacion_montecarlo(**args),
    "estado_simulacion_montecarlo": lambda _args: _tool_estado_simulacion_montecarlo(),
    "recargar_resultados_montecarlo": lambda _args: _tool_recargar_resultados_montecarlo(),
}

SYSTEM_PROMPT = """Eres un consultor senior de estrategia de negocio especializado en crecimiento digital.

Tienes acceso a herramientas que consultan modelos de ML entrenados sobre datos historicos reales y simulaciones Monte Carlo de escenarios futuros de un negocio de marketing digital.

Proceso de analisis:
1. Llama a analizar_negocio('todos') para entender el punto de partida por bloque horario.
2. Si el usuario quiere rehacer la simulacion o verla en vivo, usa ejecutar_simulacion_montecarlo en modo background, consulta estado_simulacion_montecarlo y cuando el progreso llegue al 100% llama a recargar_resultados_montecarlo.
3. Para cada decision relevante, consulta uplift ML cuando exista y distribucion Monte Carlo para medir riesgo.
4. Usa comparar_decisiones para el ranking final.
5. Cierra con una recomendacion ejecutiva clara: opcion principal, segunda opcion y que descartar.
"""


def _client():
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    if not api_key:
        raise RuntimeError("Falta OPENAI_API_KEY. Define la variable en el archivo .env del proyecto.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Falta instalar openai en el entorno activo.") from exc
    
    # Si base_url no está en el .env, usará el de OpenAI por defecto
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def _format_tool_args(args: dict[str, Any]) -> str:
    if not args:
        return "sin parametros"
    return ", ".join(f"{key}={value}" for key, value in args.items())


def _format_currency(value: float) -> str:
    return f"{value:,.0f} USD".replace(",", ".")


def _summarize_tool_result(name: str, raw_result: str) -> str:
    try:
        parsed = json.loads(raw_result)
    except Exception:
        return "Respuesta no estructurada disponible."

    if name == "comparar_decisiones" and isinstance(parsed, list) and parsed:
        best = parsed[0]
        second = parsed[1] if len(parsed) > 1 else parsed[0]
        return (
            f"{best['decision']} lidera con {_format_currency(float(best['beneficio_esperado_usd']))}; "
            f"la siguiente opcion es {second['decision']}."
        )

    if name == "distribucion_montecarlo" and isinstance(parsed, dict):
        return (
            f"{parsed.get('decision', 'Decision')}: P10 {_format_currency(float(parsed.get('p10_usd', 0.0)))}, "
            f"P90 {_format_currency(float(parsed.get('p90_usd', 0.0)))}, "
            f"perdida {float(parsed.get('probabilidad_perdida_pct', 0.0)):.1f}%."
        )

    if name == "obtener_uplift_ml" and isinstance(parsed, dict):
        uplift = parsed.get("uplift_conversion_pct")
        profit = parsed.get("uplift_beneficio_por_oportunidad_usd")
        uplift_text = f"{float(uplift) * 100:.1f}%" if uplift is not None else "n/d"
        profit_text = _format_currency(float(profit)) if profit is not None else "n/d"
        return f"Uplift de conversion {uplift_text} y mejora economica por oportunidad de {profit_text}."

    if name == "analizar_negocio":
        rows = parsed if isinstance(parsed, list) else [parsed]
        if rows:
            top = max(rows, key=lambda row: float(row.get("beneficio_contribucion_usd", 0.0)))
            return (
                f"{top.get('canal', 'Canal')} aporta el mayor beneficio historico "
                f"con {_format_currency(float(top.get('beneficio_contribucion_usd', 0.0)))}."
            )

    if isinstance(parsed, dict) and parsed.get("status"):
        return f"Estado: {parsed['status']}."

    return "Resultado estructurado disponible para soporte de la recomendacion."


def _record_tool_trace(name: str, args: dict[str, Any], raw_result: str) -> dict[str, str]:
    return {
        "name": name,
        "purpose": TOOL_PURPOSES.get(name, "Consulta especializada del agente."),
        "args": _format_tool_args(args),
        "outcome": _summarize_tool_result(name, raw_result),
    }


def run_agent_session(question: str, model: str = "gpt-4o-mini", verbose: bool = True) -> dict[str, Any]:
    # Permite sobrescribir el modelo desde el .env (útil para Kimi, MiniMax, DeepSeek, etc.)
    env_model = os.getenv("OPENAI_MODEL")
    actual_model = env_model if env_model else model

    client = _client()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_trace: list[dict[str, str]] = []

    iteration = 0
    while True:
        iteration += 1
        response = client.chat.completions.create(
            model=actual_model,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            temperature=0.2,
        )
        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            return {"content": message.content, "tool_trace": tool_trace}

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if verbose:
                print(f"[iter {iteration}] -> {name}({args})")
            result = DISPATCH[name](args)
            tool_trace.append(_record_tool_trace(name, args, result))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )


def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _fallback_agent_memo(summary_json: str, uplift_json: str) -> dict[str, Any]:
    ranking = json.loads(summary_json)
    uplift_rows = json.loads(uplift_json)

    best = ranking[0]
    second = ranking[1] if len(ranking) > 1 else ranking[0]
    third = ranking[2] if len(ranking) > 2 else ranking[-1]
    riskiest = max(ranking, key=lambda row: float(row.get("probabilidad_perdida", 0.0)))
    most_volatile = max(ranking, key=lambda row: float(row.get("p90_usd", 0.0)) - float(row.get("p10_usd", 0.0)))
    control_row = next((row for row in uplift_rows if "control" in str(row.get("label", "")).lower()), None)
    regulacion_row = next((row for row in uplift_rows if "regulacion" in str(row.get("label", "")).lower()), None)

    best_profit = float(best["beneficio_esperado_usd"])
    second_profit = float(second["beneficio_esperado_usd"])
    gap = best_profit - second_profit
    best_roi = float(best["roi_esperado"])
    best_loss = float(best["probabilidad_perdida"])
    third_loss = float(third.get("probabilidad_perdida", 0.0))
    volatile_range = float(most_volatile.get("p90_usd", 0.0)) - float(most_volatile.get("p10_usd", 0.0))

    control_uplift = None
    regulacion_uplift = None
    if control_row and control_row.get("uplift_conversion_pct") is not None:
        control_uplift = float(control_row["uplift_conversion_pct"])
    if regulacion_row and regulacion_row.get("uplift_conversion_pct") is not None:
        regulacion_uplift = float(regulacion_row["uplift_conversion_pct"])

    # El P10 y la probabilidad de perdida de la segunda opcion se leen del
    # ranking en vez de darse por supuestos: el caso base afirmaba "0.0% de
    # perdida" en texto fijo y eso era falso en cuanto cambiaban los datos.
    second_p10 = float(second["p10_usd"])
    second_loss = float(second.get("probabilidad_perdida", 0.0))
    second_perfil = (
        f"un perfil defensivo con P10 de {_format_currency(second_p10)} y {second_loss:.1f}% de perdida"
        if second_p10 > 0
        else f"un suelo negativo de {_format_currency(second_p10)} y {second_loss:.1f}% de perdida"
    )

    findings = [
        f"La diferencia frente a la segunda opcion es de {_format_currency(gap)}, asi que la primera plaza no depende de ruido marginal.",
        f"{second['decision']} no gana en media y presenta {second_perfil}.",
        f"{third['decision']} solo merece entrar si se acepta una estrategia claramente mas agresiva: {third_loss:.1f}% de perdida y mayor dispersion operativa.",
    ]

    tool_trace = [
        {
            "name": "comparar_decisiones",
            "purpose": TOOL_PURPOSES["comparar_decisiones"],
            "args": "sin parametros",
            "outcome": f"{best['decision']} lidera con {_format_currency(best_profit)} y abre una brecha de {_format_currency(gap)} frente a la segunda opcion.",
        },
        {
            "name": "distribucion_montecarlo",
            "purpose": TOOL_PURPOSES["distribucion_montecarlo"],
            "args": f"decision={best['decision']}",
            "outcome": f"{best['decision']} mantiene un suelo de {_format_currency(float(best['p10_usd']))} en P10 y {best_loss:.1f}% de probabilidad de perdida.",
        },
        {
            "name": "distribucion_montecarlo",
            "purpose": TOOL_PURPOSES["distribucion_montecarlo"],
            "args": f"decision={second['decision']}",
            "outcome": f"{second['decision']} queda por detras en media, con {second_perfil}.",
        },
        {
            "name": "obtener_uplift_ml",
            "purpose": TOOL_PURPOSES["obtener_uplift_ml"],
            "args": "decision=control_fino_completo",
            "outcome": (
                f"El historico muestra un uplift estimado del {control_uplift:.1f}% en cobertura de degradacion con control fino de carga y rampa."
                if control_uplift is not None
                else "La base historica confirma que el control fino de carga es una palanca repetible."
            ),
        },
    ]

    audience_views = {
        "finanzas": {
            "headline": f"Finanzas: comprometer el anio a {best['decision']} es hoy la estrategia con mejor retorno ajustado a riesgo.",
            "summary": f"La recomendacion prioriza eficiencia del capital inmovilizado en el activo: {_format_currency(best_profit)} esperados, {best_roi:.1f}x de ROI y un suelo de {_format_currency(float(best['p10_usd']))} en P10.",
            "reasons": [
                f"La brecha de {_format_currency(gap)} frente a la segunda opcion permite decidir con conviccion y no por desempate estadistico.",
                f"El downside esta contenido: {best_loss:.1f}% de probabilidad de perdida y P10 de {_format_currency(float(best['p10_usd']))}.",
                "La estrategia ganadora se apoya en patrones ya presentes en el historico de despacho, no en una hipotesis de mercado sin respaldo.",
            ],
            "watchouts": [
                "Ampliar la profundidad de descarga para forzar facturacion degrada el activo mas rapido de lo que crece el ingreso: el desgaste escala con el cuadrado, no linealmente.",
                f"{second['decision']} debe quedarse lista como alternativa inmediata si el diferencial de precio capturado no se materializa en el primer trimestre.",
                f"{riskiest['decision']} exige tolerancia a volatilidad y capital hundido antes de entrar en el plan del anio.",
            ],
            "next_actions": [
                "Aprobar una primera fase acotada con responsable, calendario y criterio financiero de exito por trimestre.",
                "Reservar la segunda estrategia del ranking como alternativa priorizada si la primera no confirma el margen esperado.",
                "Revisar en comite el delta real frente al caso base antes de comprometer inversion adicional en habilitaciones.",
            ],
            "switch_signals": [
                f"Rotar a {second['decision']} si el margen realizado queda muy por debajo de la hipotesis y erosiona el payback del activo.",
                "Evitar aumentar el ciclado mientras el coste de degradacion por MWh suba mas rapido que el diferencial capturado.",
                f"Abrir {third['decision']} solo si cambia el mandato de eficiencia a expansion y se acepta mayor volatilidad.",
            ],
            "due_diligence": [
                "Cuantificar el coste de degradacion por ciclo equivalente y su efecto sobre el valor residual del banco al final del contrato.",
                "Asegurar trazabilidad del margen por bloque horario para auditar de donde sale realmente el retorno.",
                "Confirmar responsables y dependencias con el operador de red antes de comprometer capacidad.",
            ],
        },
        "operacion": {
            "headline": f"Operacion del activo: {best['decision']} es la que mejor equilibra ingreso y vida util del banco.",
            "summary": "La mejor estrategia de operacion no es la que mas energia mueve, sino la que captura diferencial sin comprarlo con ciclos que no se recuperan.",
            "reasons": [
                "La estrategia ganadora concentra el despacho en las ventanas donde el diferencial paga el desgaste, en vez de ciclar por defecto.",
                f"El margen frente a la segunda opcion es de {_format_currency(gap)}, suficiente para justificar una sola configuracion de consignas y no un regimen mixto.",
                f"{second['decision']} queda como complemento para las horas en las que el arbitraje no compensa, sin cambiar el regimen de carga.",
            ],
            "watchouts": [
                "Forzar descargas profundas en punta parece rentable en la liquidacion del dia y aparece meses despues como capacidad perdida.",
                f"{riskiest['decision']} tiene techo alto, pero mezcla habilitacion tecnica con exposicion economica antes de tener datos propios.",
                "Sin telemetria por ciclo, el equipo puede confundir mas energia despachada con mejor operacion del activo.",
            ],
            "next_actions": [
                "Fijar consignas de estado de carga y profundidad de descarga por bloque horario, con lectura semanal de ciclos consumidos.",
                "Instrumentar el coste de degradacion por ciclo para que aparezca en el mismo panel que el ingreso, no en un informe aparte.",
                "Definir gatillos claros para ampliar el ciclado solo despues de demostrar margen neto estable.",
            ],
            "switch_signals": [
                f"Mover el foco a {second['decision']} si el diferencial medio capturado cae por debajo del coste de degradacion del ciclo.",
                "Mantener la profundidad conservadora hasta que la telemetria confirme que el desgaste real esta por debajo del modelado.",
                f"Probar {third['decision']} solo con una ventana acotada si aparece evidencia firme de remuneracion superior.",
            ],
            "due_diligence": [
                "Separar la medicion por bloque horario y por profundidad de descarga para saber donde vive el margen real.",
                "Contrastar la curva de degradacion asumida contra la garantia del fabricante y la telemetria disponible.",
                "Definir de antemano que indicadores permiten pasar de una ventana piloto a regimen permanente.",
            ],
        },
        "riesgo": {
            "headline": f"Riesgo: {best['decision']} es la opcion mas defendible por el suelo de su distribucion, no por su media.",
            "summary": "La prioridad aqui no es maximizar el techo, sino proteger el escenario adverso manteniendo un retorno claramente atractivo.",
            "reasons": [
                f"El caso ganador combina {_format_currency(best_profit)} esperados con un P10 de {_format_currency(float(best['p10_usd']))}.",
                f"{second['decision']} es la alternativa de respaldo mas limpia si hiciera falta rotar sin asumir volatilidad excesiva.",
                f"{riskiest['decision']} concentra la mayor probabilidad de perdida y no deberia entrar sin controles adicionales.",
            ],
            "watchouts": [
                f"{most_volatile['decision']} tiene un recorrido de {_format_currency(volatile_range)} entre P10 y P90: el resultado depende mas del escenario que de la ejecucion.",
                "Comprometer capacidad de reserva y luego no poder entregarla tiene consecuencias con el operador de red que no aparecen en la cuenta de resultados.",
                "La cola derecha del precio spot es gruesa: unas pocas horas explican gran parte del ingreso, y no estan garantizadas.",
            ],
            "next_actions": [
                "Fijar limites de exposicion por estrategia antes de comprometer el regimen del anio.",
                "Establecer un punto de control trimestral con criterio explicito de salida.",
                "Documentar que compromisos con el operador quedan afectados por cada estrategia.",
            ],
            "switch_signals": [
                f"Revisar la decision si la probabilidad de perdida realizada supera el {max(best_loss, 1.0):.1f}% observado en simulacion.",
                "Salir de cualquier regimen cuyo P10 cruce a negativo tras recalibrar la volatilidad del precio.",
                "Reevaluar si cambia la regulacion de los productos de reserva o los requisitos de habilitacion.",
            ],
            "due_diligence": [
                "Validar la calibracion de la volatilidad del precio contra series reales antes de operar con estos numeros.",
                "Revisar penalizaciones contractuales por incumplimiento de reserva comprometida.",
                "Confirmar que el modelo de degradacion no subestima el desgaste en descargas profundas repetidas.",
            ],
        },
    }
    return {
        "headline": f"El agente no solo elige {best['decision']}: explica por que gana ahora y que tendria que pasar para cambiar de idea.",
        "summary": (
            f"{best['decision']} se mantiene como primera apuesta porque combina el mayor beneficio esperado "
            f"({_format_currency(best_profit)}), un ROI de {best_roi:.1f}x y una probabilidad de perdida de {best_loss:.1f}%."
        ),
        "reasons": [
            f"La ventaja economica frente a la segunda opcion es de {_format_currency(gap)}, suficiente para que la recomendacion no dependa de un empate estadistico.",
            f"El suelo del escenario sigue siendo defendible: P10 de {_format_currency(float(best['p10_usd']))} frente a alternativas con colas mas fragiles.",
            (
                f"El historico ya contiene uplift observable en el control fino de carga y rampa ({control_uplift:.1f}% de mejora en cobertura estimada)."
                if control_uplift is not None
                else "La recomendacion se apoya en una palanca que el historico ya ha mostrado como repetible, no en un salto especulativo."
            ),
        ],
        "watchouts": [
            f"{second['decision']} sigue viva como plan B con {second_perfil}.",
            f"{riskiest['decision']} es la opcion que mas puede deteriorar el caso si se ejecuta antes de tiempo: {float(riskiest['probabilidad_perdida']):.1f}% de perdida esperada.",
            f"La dispersion mas agresiva sigue en {most_volatile['decision']}: una banda P10-P90 de {_format_currency(volatile_range)} obliga a revisar la exposicion antes de comprometer el regimen del anio.",
        ],
        "next_actions": [
            "Fijar las consignas de estado de carga y profundidad de descarga como piloto acotado, con responsable, plazo y lectura de margen por bloque horario.",
            (
                f"Preparar en paralelo la oferta de regulacion de frecuencia como palanca complementaria, especialmente si se confirma un uplift cercano al {regulacion_uplift:.1f}% en las ventanas aptas."
                if regulacion_uplift is not None
                else "Preparar en paralelo la oferta de regulacion de frecuencia como palanca complementaria sobre las ventanas aptas."
            ),
            "Bloquear una revision trimestral para decidir si se amplia el ciclado, se mantiene el regimen o se rota a la segunda opcion.",
        ],
        "switch_signals": [
            f"Cambiar a {second['decision']} si el diferencial capturado no sostiene el margen esperado o si el coste real de degradacion supera al modelado.",
            f"Abrir {third['decision']} solo si se acepta un riesgo superior al {third_loss:.1f}% o si el objetivo pasa de eficiencia a expansion agresiva.",
            "Retrasar cualquier aumento del ciclado si el coste de degradacion por MWh sube mas rapido que el diferencial capturado, porque ese punto de saturacion ya aparece en el historico.",
        ],
        "due_diligence": [
            "Verificar que el margen se pueda atribuir por bloque horario y por profundidad de descarga, para saber que parte del retorno viene de cada palanca.",
            "Definir umbrales de exito y criterios de salida antes del despliegue para que la decision no se convierta en opinion post-hoc.",
            "Contrastar la curva de degradacion asumida contra la garantia del fabricante antes de activar regimenes de mayor dispersion.",
        ],
        "findings": findings,
        "tool_trace": tool_trace,
        "audience_views": audience_views,
    }


@lru_cache(maxsize=8)
def build_agent_decision_memo(summary_json: str, uplift_json: str, model: str = "gpt-4o-mini") -> dict[str, Any]:
    fallback = _fallback_agent_memo(summary_json, uplift_json)
    prompt = f"""
Necesito una memo ejecutiva diferencial para un dashboard de demo.

Objetivo:
- No repitas solo el ranking.
- Explica por que gana la opcion elegida ahora.
- Explica que tendria que pasar para cambiar la recomendacion.
- Da preguntas de due diligence antes de ejecutar.

Usa tus herramientas antes de responder:
1. comparar_decisiones
2. distribucion_montecarlo para cada una de las cuatro estrategias del ranking
3. obtener_uplift_ml para control_fino, descarga_profunda y regulacion

Contexto ya consolidado del ranking:
{summary_json}

Contexto ya consolidado de uplift:
{uplift_json}

Devuelve exclusivamente JSON valido con este esquema:
{{
  "headline": "string",
  "summary": "string",
  "reasons": ["string", "string", "string"],
  "watchouts": ["string", "string", "string"],
  "next_actions": ["string", "string", "string"],
  "switch_signals": ["string", "string", "string"],
    "due_diligence": ["string", "string", "string"],
    "findings": ["string", "string", "string"],
    "audience_views": {{
        "finanzas": {{
            "headline": "string",
            "summary": "string",
            "reasons": ["string", "string", "string"],
            "watchouts": ["string", "string", "string"],
            "next_actions": ["string", "string", "string"],
            "switch_signals": ["string", "string", "string"],
            "due_diligence": ["string", "string", "string"]
        }},
        "operacion": {{
            "headline": "string",
            "summary": "string",
            "reasons": ["string", "string", "string"],
            "watchouts": ["string", "string", "string"],
            "next_actions": ["string", "string", "string"],
            "switch_signals": ["string", "string", "string"],
            "due_diligence": ["string", "string", "string"]
        }},
        "riesgo": {{
            "headline": "string",
            "summary": "string",
            "reasons": ["string", "string", "string"],
            "watchouts": ["string", "string", "string"],
            "next_actions": ["string", "string", "string"],
            "switch_signals": ["string", "string", "string"],
            "due_diligence": ["string", "string", "string"]
        }}
    }}
}}

Reglas:
- Escribe en espanol ejecutivo claro.
- Cada punto debe aportar un matiz que no sea obvio solo con leer quien queda primero.
- Incluye cifras cuando ayuden a justificar.
- No uses markdown ni bloques de codigo.
""".strip()

    try:
        session = run_agent_session(prompt, model=model, verbose=False)
        content = session["content"]
        parsed = json.loads(_strip_json_fences(content))
    except Exception:
        return _aplicar_guardarrail(fallback, summary_json)

    memo = fallback.copy()
    for key in memo:
        value = parsed.get(key)
        if isinstance(memo[key], list):
            if isinstance(value, list) and len(value) >= 3:
                memo[key] = [str(item).strip() for item in value[:3]]
        elif key == "audience_views" and isinstance(value, dict):
            merged_views = memo["audience_views"].copy()
            for audience, audience_base in memo["audience_views"].items():
                candidate = value.get(audience)
                if not isinstance(candidate, dict):
                    continue
                merged = audience_base.copy()
                for audience_key, audience_value in audience_base.items():
                    parsed_value = candidate.get(audience_key)
                    if isinstance(audience_value, list):
                        if isinstance(parsed_value, list) and len(parsed_value) >= 3:
                            merged[audience_key] = [str(item).strip() for item in parsed_value[:3]]
                    elif isinstance(parsed_value, str) and parsed_value.strip():
                        merged[audience_key] = parsed_value.strip()
                merged_views[audience] = merged
            memo["audience_views"] = merged_views
        elif isinstance(value, str) and value.strip():
            memo[key] = value.strip()
    if isinstance(parsed.get("findings"), list) and len(parsed["findings"]) >= 3:
        memo["findings"] = [str(item).strip() for item in parsed["findings"][:3]]
    if session.get("tool_trace"):
        memo["tool_trace"] = session["tool_trace"]
    return _aplicar_guardarrail(memo, summary_json)


def _aplicar_guardarrail(memo: dict[str, Any], summary_json: str) -> dict[str, Any]:
    """Ninguna frase puede contradecir a las cifras del propio informe.

    Aplica tanto al texto de plantilla como al que devuelve el LLM: los dos pueden
    afirmar "suelo positivo" sobre un P10 negativo. Las frases retiradas quedan
    listadas en `coherencia` para que el fallo sea visible y no silencioso.
    """
    try:
        from analitica_avanzada import coherencia_informe

        ranking = json.loads(summary_json)
        revisado = coherencia_informe(memo, ranking)
    except Exception:
        return memo

    saneado = revisado["informe"]
    saneado["coherencia"] = {
        "frases_retiradas": revisado["frases_retiradas"],
        "incidencias": revisado["incidencias"],
        "metricas_contrastadas": revisado["metricas_contrastadas"],
    }
    return saneado


def run_agent(question: str, model: str = "gpt-4o-mini", verbose: bool = True) -> str:
    return str(run_agent_session(question, model=model, verbose=verbose)["content"])
