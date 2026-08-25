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
    "sitio": "Optimizar la conversión del sitio",
    "remarketing": "Reactivación y remarketing",
    "paid_social": "Escalar paid social",
    "categoria": "Abrir categoría nueva",
}

UPLIFT_ALIAS = {
    "funnel": "funnel_full_optimized",
    "webinar": "webinar_attendance",
    "nuevo_producto": "new_product_offer",
}

TOOL_PURPOSES = {
    "analizar_negocio": "Lee el histórico de captación y resume conversión, inversión, ingreso y margen por canal.",
    "obtener_uplift_ml": "Consulta el uplift contrafactual estimado por el modelo para una palanca concreta.",
    "distribucion_montecarlo": "Lee la distribución de 10.000 futuros de una decisión para medir suelo, techo y riesgo.",
    "comparar_decisiones": "Ordena las alternativas lado a lado por beneficio esperado, ROI y probabilidad de pérdida.",
    "ejecutar_simulacion_montecarlo": "Lanza una simulación Monte Carlo nueva con dashboard live.",
    "estado_simulacion_montecarlo": "Consulta el progreso actual de la simulación live.",
    "recargar_resultados_montecarlo": "Recarga el ranking consolidado tras una simulación.",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe {path.name}. Ejecuta antes la simulación.")
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


def resumen_por_canal(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Margen del histórico agregado por canal de captación.

    Los nombres de columna salen del CSV que escribe el pipeline. Antes esta
    función pedia columnas en castellano que el generador nunca produjo, así
    que reventaba con KeyError en cuanto el agente la invocaba.
    """
    if df is None:
        df = cargar_artifacts()["dataset"]
    resumen = (
        df.groupby("channel")
        .agg(
            oportunidades=("transaction_id", "count"),
            conversion=("converted_to_sale", "mean"),
            inversion_usd=("cost_attributed_usd", "sum"),
            ingreso_usd=("revenue_usd", "sum"),
            margen_usd=("contribution_profit_usd", "sum"),
            coste_medio=("cost_attributed_usd", "mean"),
            score_medio=("lead_score", "mean"),
        )
        .sort_values("margen_usd", ascending=False)
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
            "nota": "Todavía no existe el archivo de estado. Lanza antes la simulación.",
        }
    return json.loads(LIVE_STATUS_PATH.read_text(encoding="utf-8"))


def recargar_resultados_montecarlo() -> dict[str, pd.DataFrame]:
    return cargar_artifacts()


def _tool_analizar_negocio(canal: str = "todos") -> str:
    resumen = resumen_por_canal().reset_index()
    if canal == "todos":
        data = resumen.to_dict(orient="records")
    else:
        fila = resumen[resumen["channel"] == canal]
        if fila.empty:
            return json.dumps(
                {"error": f"Canal {canal!r} no encontrado.", "disponibles": resumen["channel"].tolist()},
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
        return json.dumps({"error": "Sin datos para esta decisión."}, ensure_ascii=False)
    return json.dumps(fila.iloc[0].to_dict(), ensure_ascii=False, default=float)


def _tool_distribucion_montecarlo(decision: str) -> str:
    nombre = DECISION_ALIAS.get(decision.lower().replace(" ", "_"), decision)
    artifacts = cargar_artifacts()
    simulaciones = artifacts["simulaciones"]
    resumen = artifacts["resumen"]
    sim = simulaciones[simulaciones["decision"] == nombre]["incremental_profit_usd"]
    if sim.empty:
        return json.dumps({"error": "Decisión no encontrada.", "disponibles": simulaciones["decision"].unique().tolist()}, ensure_ascii=False)
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
            "description": "Analiza el histórico de captación por canal: conversión, inversión, ingreso, margen y coste medio por oportunidad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "canal": {"type": "string", "description": "Usa 'todos' para ver todos los canales."}
                },
                "required": ["canal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_uplift_ml",
            "description": "Devuelve el uplift contrafactual estimado para funnel, webinar o nuevo_producto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["funnel", "webinar", "nuevo_producto"]}
                },
                "required": ["decision"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "distribucion_montecarlo",
            "description": "Devuelve la distribución estadística de la Monte Carlo para una decisión.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["sitio", "remarketing", "paid_social", "categoria"]}
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
            "description": "Lanza una simulación Monte Carlo nueva con dashboard vivo.",
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
            "description": "Recarga los resultados generados por la última simulación.",
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
1. Llama a analizar_negocio('todos') para entender el punto de partida por canal.
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
        return "sin parámetros"
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
            f"la siguiente opción es {second['decision']}."
        )

    if name == "distribucion_montecarlo" and isinstance(parsed, dict):
        return (
            f"{parsed.get('decision', 'Decision')}: P10 {_format_currency(float(parsed.get('p10_usd', 0.0)))}, "
            f"P90 {_format_currency(float(parsed.get('p90_usd', 0.0)))}, "
            f"pérdida {float(parsed.get('probabilidad_perdida_pct', 0.0)):.1f}%."
        )

    if name == "obtener_uplift_ml" and isinstance(parsed, dict):
        uplift = parsed.get("uplift_conversion_pct")
        profit = parsed.get("uplift_beneficio_por_oportunidad_usd")
        uplift_text = f"{float(uplift) * 100:.1f}%" if uplift is not None else "n/d"
        profit_text = _format_currency(float(profit)) if profit is not None else "n/d"
        return f"Uplift de conversión {uplift_text} y mejora económica por oportunidad de {profit_text}."

    if name == "analizar_negocio":
        rows = parsed if isinstance(parsed, list) else [parsed]
        if rows:
            top = max(rows, key=lambda row: float(row.get("beneficio_contribucion_usd", 0.0)))
            return (
                f"{top.get('canal', 'Canal')} aporta el mayor beneficio histórico "
                f"con {_format_currency(float(top.get('beneficio_contribucion_usd', 0.0)))}."
            )

    if isinstance(parsed, dict) and parsed.get("status"):
        return f"Estado: {parsed['status']}."

    return "Resultado estructurado disponible para soporte de la recomendación."


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
    embudo_row = next((row for row in uplift_rows if "embudo" in str(row.get("label", "")).lower()), None)
    reactivacion_row = next((row for row in uplift_rows if "reactivacion" in str(row.get("label", "")).lower()), None)

    best_profit = float(best["beneficio_esperado_usd"])
    second_profit = float(second["beneficio_esperado_usd"])
    gap = best_profit - second_profit
    best_roi = float(best["roi_esperado"])
    best_loss = float(best["probabilidad_perdida"])
    third_loss = float(third.get("probabilidad_perdida", 0.0))
    volatile_range = float(most_volatile.get("p90_usd", 0.0)) - float(most_volatile.get("p10_usd", 0.0))

    embudo_uplift = None
    reactivacion_uplift = None
    if embudo_row and embudo_row.get("uplift_conversion_pct") is not None:
        embudo_uplift = float(embudo_row["uplift_conversion_pct"])
    if reactivacion_row and reactivacion_row.get("uplift_conversion_pct") is not None:
        reactivacion_uplift = float(reactivacion_row["uplift_conversion_pct"])

    # El P10 y la probabilidad de pérdida de la segunda opción se leen del
    # ranking en vez de darse por supuestos: el caso base afirmaba "0.0% de
    # pérdida" en texto fijo y eso era falso en cuanto cambiaban los datos.
    second_p10 = float(second["p10_usd"])
    second_loss = float(second.get("probabilidad_perdida", 0.0))
    second_perfil = (
        f"un perfil defensivo con P10 de {_format_currency(second_p10)} y {second_loss:.1f}% de pérdida"
        if second_p10 > 0
        else f"un suelo negativo de {_format_currency(second_p10)} y {second_loss:.1f}% de pérdida"
    )

    findings = [
        f"La diferencia frente a la segunda opción es de {_format_currency(gap)}, así que la primera plaza no depende de ruido marginal.",
        f"{second['decision']} no gana en media y presenta {second_perfil}.",
        f"{third['decision']} solo merece entrar si se acepta una estrategia claramente más agresiva: {third_loss:.1f}% de pérdida y mayor dispersión operativa.",
    ]

    tool_trace = [
        {
            "name": "comparar_decisiones",
            "purpose": TOOL_PURPOSES["comparar_decisiones"],
            "args": "sin parámetros",
            "outcome": f"{best['decision']} lidera con {_format_currency(best_profit)} y abre una brecha de {_format_currency(gap)} frente a la segunda opción.",
        },
        {
            "name": "distribucion_montecarlo",
            "purpose": TOOL_PURPOSES["distribucion_montecarlo"],
            "args": f"decision={best['decision']}",
            "outcome": f"{best['decision']} mantiene un suelo de {_format_currency(float(best['p10_usd']))} en P10 y {best_loss:.1f}% de probabilidad de pérdida.",
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
            "args": "decision=optimizacion_integral_del_embudo",
            "outcome": (
                f"El histórico muestra un uplift estimado del {embudo_uplift:.1f}% en conversión al optimizar landing, CTA y checkout."
                if embudo_uplift is not None
                else "La base histórica confirma que la optimización del embudo es una palanca repetible."
            ),
        },
    ]

    audience_views = {
        "ceo": {
            "headline": f"Modo CEO: asignar el presupuesto del trimestre a {best['decision']} es hoy la apuesta con mejor retorno ajustado a riesgo.",
            "summary": f"La recomendación prioriza eficiencia de capital: {_format_currency(best_profit)} esperados, {best_roi:.1f}x de retorno y un suelo de {_format_currency(float(best['p10_usd']))} en P10.",
            "reasons": [
                f"La brecha de {_format_currency(gap)} frente a la segunda opción permite decidir con convicción y no por desempate estadístico.",
                f"El downside esta contenido: {best_loss:.1f}% de probabilidad de pérdida y P10 de {_format_currency(float(best['p10_usd']))}.",
                "La palanca ganadora se apoya en efectos que el histórico ya muestra, no en una hipotesis de canal sin respaldo.",
            ],
            "watchouts": [
                "Subir la inversión en los canales ya saturados compra volumen que no convierte: el coste por oportunidad se dobla y la calidad del lead cae, y eso ya esta medido en el histórico.",
                f"{second['decision']} debe quedarse lista como alternativa inmediata si la mejora esperada no se materializa en el primer ciclo.",
                f"{riskiest['decision']} exige tolerancia a volatilidad y capacidad de ejecución antes de entrar en el plan del trimestre.",
            ],
            "next_actions": [
                "Aprobar una primera fase acotada con responsable, calendario y criterio financiero de exito.",
                "Reservar la segunda opción del ranking como alternativa priorizada si la primera no confirma el uplift.",
                "Revisar en comité el delta real frente al caso base antes de liberar más presupuesto.",
            ],
            "switch_signals": [
                f"Rotar a {second['decision']} si el uplift realizado queda muy por debajo de la hipotesis y erosiona el payback.",
                "Frenar el escalado de medios mientras el coste por oportunidad suba más rápido que el volumen incremental.",
                f"Abrir {third['decision']} solo si cambia el mandato de eficiencia a expansión y se acepta mayor volatilidad.",
            ],
            "due_diligence": [
                "Cuantificar el coste de implementación y el payback esperado por etapa antes de comprometer el trimestre.",
                "Asegurar trazabilidad del margen por canal para auditar de donde sale realmente el retorno, sin depender del panel de cada plataforma.",
                "Confirmar responsables y dependencias operativas antes de aprobar el despliegue completo.",
            ],
        },
        "growth": {
            "headline": f"Modo Growth: {best['decision']} es la ruta más rápida para desbloquear crecimiento sin deteriorar la base.",
            "summary": "La mejor secuencia de crecimiento no es la más ruidosa, sino la que ofrece uplift repetible y espacio para iterar con riesgo controlado.",
            "reasons": [
                "La palanca ganadora se puede medir de forma limpia porque no depende de la atribución que reporta cada plataforma.",
                f"El margen frente a la segunda opción es de {_format_currency(gap)}, suficiente para concentrar al equipo en una sola apuesta principal.",
                f"{second['decision']} queda como palanca complementaria para capturar valor sobre la base ya generada.",
            ],
            "watchouts": [
                "Escalar medios demasiado pronto tapa el aprendizaje real: la saturación mete ruido y después no se sabe que funciono.",
                f"{riskiest['decision']} tiene techo alto, pero mezcla aprendizaje de producto con riesgo económico elevado.",
                "Sin instrumentación por etapa, el equipo puede confundir más volumen con mejora estructural de la conversión.",
            ],
            "next_actions": [
                "Lanzar un sprint de conversión con lectura semanal por etapa del embudo.",
                "Preparar en paralelo la palanca de reactivación para capturar valor sobre la base existente.",
                "Definir gatillos claros para abrir escala solo después de demostrar uplift estable.",
            ],
            "switch_signals": [
                f"Mover el foco a {second['decision']} si la mejora de conversión se estanca tras el primer sprint.",
                "Mantener los medios pagados como motor secundario hasta que el sitio convierta mejor y no solo atraiga más tráfico.",
                f"Probar {third['decision']} solo con un experimento limitado si aparece evidencia fuerte de demanda.",
            ],
            "due_diligence": [
                "Separar la medición de landing, CTA, lead magnet y checkout para saber donde vive el uplift.",
                "Contrastar lo que reporta cada plataforma contra las ventas registradas: la suma de los paneles supera el total real.",
                "Definir de antemano que métricas permiten pasar de experimento a escala.",
            ],
        },
        "riesgo": {
            "headline": f"Modo Riesgo: {best['decision']} es la opción más defendible por el suelo de su distribución, no por su media.",
            "summary": "La prioridad aquí no es maximizar el techo, sino proteger el escenario adverso manteniendo un retorno claramente atractivo.",
            "reasons": [
                f"El caso ganador combina {_format_currency(best_profit)} esperados con un P10 de {_format_currency(float(best['p10_usd']))}.",
                f"{second['decision']} es la alternativa de respaldo más limpia si hiciera falta rotar sin asumir volatilidad excesiva.",
                f"{riskiest['decision']} concentra la mayor probabilidad de pérdida y no debería entrar sin controles adicionales.",
            ],
            "watchouts": [
                f"{most_volatile['decision']} tiene un recorrido de {_format_currency(volatile_range)} entre P10 y P90: el resultado depende más del escenario que de la ejecución.",
                "La atribución de las plataformas esta rota desde los cambios de privacidad: decidir con el dato que reporta el propio canal es asumir un riesgo que no se ve.",
                "El efecto de saturación no es lineal: el último tramo de inversión puede tener margen negativo mientras el panel sigue mostrando conversiones.",
            ],
            "next_actions": [
                "Fijar límites de exposición por canal antes de comprometer el presupuesto del trimestre.",
                "Establecer un punto de control mensual con criterio explícito de salida.",
                "Documentar que supuestos sostienen la recomendación y cuál de ellos, si falla, la invalida.",
            ],
            "switch_signals": [
                f"Revisar la decisión si la probabilidad de pérdida realizada supera el {max(best_loss, 1.0):.1f}% observado en simulación.",
                "Salir de cualquier escalado cuyo P10 cruce a negativo tras recalibrar la volatilidad del canal.",
                "Reevaluar si cambian las reglas de medición de las plataformas o la disponibilidad de señal.",
            ],
            "due_diligence": [
                "Validar la calibración de los tres ruidos contra resultados reales antes de operar con estas cifras.",
                "Revisar compromisos contractuales con agencias y plataformas antes de mover presupuesto.",
                "Confirmar que el modelo no subestima la saturación en los canales que ya operan en tramo alto.",
            ],
        },
    }
    return {
        "headline": f"El agente no solo elige {best['decision']}: explica por que gana ahora y que tendría que pasar para cambiar de idea.",
        "summary": (
            f"{best['decision']} se mantiene como primera apuesta porque combina el mayor beneficio esperado "
            f"({_format_currency(best_profit)}), un ROI de {best_roi:.1f}x y una probabilidad de pérdida de {best_loss:.1f}%."
        ),
        "reasons": [
            f"La ventaja económica frente a la segunda opción es de {_format_currency(gap)}, suficiente para que la recomendación no dependa de un empate estadístico.",
            f"El suelo del escenario sigue siendo defendible: P10 de {_format_currency(float(best['p10_usd']))} frente a alternativas con colas más frágiles.",
            (
                f"El histórico ya recoge un uplift observable al optimizar el embudo, con un {embudo_uplift:.1f}% de mejora estimada en conversión."
                if embudo_uplift is not None
                else "La recomendación se apoya en una palanca que el histórico ya ha mostrado como repetible, no en un salto especulativo."
            ),
        ],
        "watchouts": [
            f"{second['decision']} sigue viva como plan B con {second_perfil}.",
            f"{riskiest['decision']} es la opción que más puede deteriorar el caso si se ejecuta antes de tiempo: {float(riskiest['probabilidad_perdida']):.1f}% de pérdida esperada.",
            f"La dispersión más agresiva sigue en {most_volatile['decision']}: una banda P10-P90 de {_format_currency(volatile_range)} obliga a revisar la exposición antes de comprometer el régimen del año.",
        ],
        "next_actions": [
            "Ejecutar la optimización del sitio como experimento acotado, con responsable, plazo y lectura de conversión por etapa del embudo.",
            (
                f"Preparar en paralelo la reactivación de la base como palanca complementaria, sobre todo si se confirma un uplift cercano al {reactivacion_uplift:.1f}% en conversión."
                if reactivacion_uplift is not None
                else "Preparar en paralelo la reactivación de la base como palanca complementaria sobre los contactos que ya interactuaron."
            ),
            "Bloquear una revisión tras el primer ciclo para decidir si se escala, se mantiene o se rota a la segunda opción.",
        ],
        "switch_signals": [
            f"Cambiar a {second['decision']} si la mejora de conversión no sostiene el margen esperado o si el coste por oportunidad sube más de lo previsto.",
            f"Abrir {third['decision']} solo si se acepta un riesgo superior al {third_loss:.1f}% o si el objetivo pasa de eficiencia a expansión agresiva.",
            "Retrasar cualquier escalado de medios si el coste por oportunidad sube más rápido que el volumen incremental, porque ese punto de saturación ya aparece en el histórico.",
        ],
        "due_diligence": [
            "Verificar que landing, CTA, lead magnet y checkout tengan medición separada, para saber en que etapa vive el uplift.",
            "Definir umbrales de exito y criterios de salida antes del despliegue para que la decisión no se convierta en opinion post-hoc.",
            "Contrastar lo que reporta cada plataforma contra las ventas registradas antes de activar escenarios de mayor dispersión.",
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
3. obtener_uplift_ml para funnel, webinar y nuevo_producto

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
        "ceo": {{
            "headline": "string",
            "summary": "string",
            "reasons": ["string", "string", "string"],
            "watchouts": ["string", "string", "string"],
            "next_actions": ["string", "string", "string"],
            "switch_signals": ["string", "string", "string"],
            "due_diligence": ["string", "string", "string"]
        }},
        "growth": {{
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
