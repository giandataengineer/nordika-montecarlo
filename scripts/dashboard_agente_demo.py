from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

try:
    from .agente_montecarlo import build_agent_decision_memo
    from .simulacion_montecarlo import (
      FEATURES,
        DATASET_PATH,
        DASHBOARDS_DIR,
        LIVE_DASHBOARD_PATH,
        PARAMS_PATH,
        REPORT_PATH,
      SEED,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
      build_aov_model,
      build_conversion_model,
      simulate_decisions,
      split_boundary,
      temporal_split,
        write_live_dashboard,
    )
except ImportError:
    from agente_montecarlo import build_agent_decision_memo
    from simulacion_montecarlo import (
      FEATURES,
        DATASET_PATH,
        DASHBOARDS_DIR,
        LIVE_DASHBOARD_PATH,
        PARAMS_PATH,
        REPORT_PATH,
      SEED,
        SIMULATIONS_PATH,
        SUMMARY_PATH,
      build_aov_model,
      build_conversion_model,
      simulate_decisions,
      split_boundary,
      temporal_split,
        write_live_dashboard,
    )


MISSION_DASHBOARD_PATH = DASHBOARDS_DIR / "agente_mission_control.html"

UPLIFT_LABELS = {
  "funnel_full_optimized": "Optimización integral del embudo",
  "webinar_attendance": "Reactivación sobre base templada",
  "new_product_offer": "Oferta de categoría nueva",
}

ADS_LABELS = {
  "paid_budget_low": "Inversión contenida",
  "paid_budget_medium": "Inversión equilibrada",
  "paid_budget_high": "Inversión intensiva",
  "paid_budget_saturated": "Canal saturado",
}

UPLIFT_EXPLANATIONS = {
  "funnel_full_optimized": "Landing, CTA, lead magnet y checkout trabajando juntos. Es el paquete barato: no compra tráfico, mejora lo que ya llega.",
  "webinar_attendance": "Secuencia de reactivación sobre quienes ya interactuaron. Poco coste incremental y ticket alto, pero solo aplica a la base existente.",
  "new_product_offer": "Abrir una categoría nueva con ticket mayor. El techo de ingreso es el más alto, pero exige inversión previa y la conversión cae mientras el catalogo madura.",
}

# Nombre del operador del caso. Es ficticio a proposito: los datos son
# sinteticos y ninguna instalación real esta detras. Cambiarlo aquí lo cambia
# en toda la consola.
OPERADOR = "Nordika"
UNIDAD = "captación de pago"

STAGES = [
    {
        "key": "briefing",
        "title": "El problema",
        "eyebrow": "Fase 01",
        "tagline": (
            "Hay cuatro iniciativas sobre la mesa y presupuesto para una sola. Los "
            "paneles de Meta, Google y TikTok se atribuyen las mismas ventas, de modo "
            "que sumados reportan más conversiones de las que registra el ecommerce."
        ),
        "command": "AGENTE.PLANTEAR_LA_DECISION()",
        "duration_ms": 1100,
    },
    {
        "key": "ingesta",
        "title": "20.000 oportunidades",
        "eyebrow": "Fase 02",
        "tagline": (
            "Carga el histórico de captación con el canal, el segmento, el nivel de "
            "inversión, el coste atribuido, las variantes de landing y de CTA, y el "
            "desenlace de cada oportunidad."
        ),
        "command": "AGENTE.CARGAR_Y_VALIDAR_DATOS()",
        "duration_ms": 1400,
    },
    {
        "key": "uplift",
        "title": "Qué aporta cada palanca",
        "eyebrow": "Fase 03",
        "tagline": (
            "Estima el contrafactual sobre la misma oportunidad con una sola palanca "
            "modificada. Aquí aparece la saturación: al subir de tramo de inversión, "
            "el coste por oportunidad se duplica y la conversión se desploma."
        ),
        "command": "AGENTE.EVALUAR_MODELOS_Y_PALANCAS()",
        "duration_ms": 1500,
    },
    {
        "key": "montecarlo",
        "title": "10.000 futuros",
        "eyebrow": "Fase 04",
        "tagline": (
            "Incorpora la incertidumbre del modelo, el riesgo de ejecución y el error "
            "residual. El resultado no es una cifra, sino una distribución con su "
            "suelo, su techo y su probabilidad de pérdida."
        ),
        "command": "AGENTE.SIMULAR_10000_FUTUROS()",
        "duration_ms": 1600,
    },
    {
        "key": "reporte",
        "title": "La decisión, en dólares",
        "eyebrow": "Fase 05",
        "tagline": (
            "Tres lecturas independientes sobre las mismas cifras, desde Finanzas, "
            "Growth y Riesgo. Cuando coinciden, la decisión queda respaldada; cuando "
            "no, ese desacuerdo es precisamente lo que hay que llevar al comité."
        ),
        "command": "AGENTE.EMITIR_RECOMENDACION()",
        "duration_ms": 1500,
    },
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe {path.name}. Ejecuta antes scripts/simulacion_montecarlo.py.")
    return pd.read_csv(path)


def _currency(value: float) -> str:
    return f"{value:,.0f} USD".replace(",", ".")


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _records(df: pd.DataFrame) -> list[dict[str, object]]:
  return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _build_gain_chart(actual: pd.Series, predicted: np.ndarray) -> list[dict[str, float]]:
  ranked = pd.DataFrame({"actual": actual.to_numpy(), "predicted": predicted})
  ranked = ranked.sort_values("predicted", ascending=False).reset_index(drop=True)
  ranked["decile"] = np.minimum(9, (np.arange(len(ranked)) * 10 // max(1, len(ranked)))).astype(int) + 1
  total_conversions = max(1, int(ranked["actual"].sum()))
  total_rows = max(1, len(ranked))
  rows = []
  cumulative = 0
  for decile in range(1, 11):
    bucket = ranked[ranked["decile"] == decile]
    conversions = int(bucket["actual"].sum())
    cumulative += conversions
    rows.append(
      {
        "decile": decile,
        "avg_score": float(bucket["predicted"].mean()) if len(bucket) else 0.0,
        "conversion_rate": float(bucket["actual"].mean()) if len(bucket) else 0.0,
        "capture_pct": cumulative / total_conversions,
        "population_pct": min(1.0, (decile * len(bucket)) / total_rows if len(bucket) else decile / 10),
      }
    )
  return rows


def _build_residual_bands(residuals: np.ndarray) -> list[dict[str, object]]:
  bands = [
    ("Sobreestima > 300 USD", residuals < -300),
    ("Sobreestima 100-300 USD", (residuals >= -300) & (residuals < -100)),
    ("Ajuste fino +/- 100 USD", (residuals >= -100) & (residuals <= 100)),
    ("Infraestima 100-300 USD", (residuals > 100) & (residuals <= 300)),
    ("Infraestima > 300 USD", residuals > 300),
  ]
  return [{"label": label, "count": int(mask.sum())} for label, mask in bands]


def _analisis_avanzado(simulations, summary, dataset, conversion_model, aov_model) -> dict:
    """Las capas que el caso base no cubre: EVPI, estabilidad y sensibilidad.

    Las dos primeras salen de la matriz de escenarios que ya esta calculada, así
    que no cuestan nada. La tercera reejecuta el Monte Carlo con pocos escenarios
    porque escalar el ruido a posteriori no es equivalente a simular con el.
    """
    import numpy as np

    from analitica_avanzada import estabilidad_ranking, sensibilidad_ruidos, valor_informacion

    matriz = simulations.pivot_table(
        index="decision", columns="simulation", values="incremental_profit_usd"
    ).dropna(axis=1)
    escenarios = {str(d): matriz.loc[d].to_numpy() for d in matriz.index}

    evpi = valor_informacion(escenarios)

    # Estabilidad: re-muestrea escenarios de la propia matriz. Cada replica es una
    # realización alternativa del mismo experimento, sin reentrenar nada.
    n_cols = matriz.shape[1]
    nombres = list(matriz.index)

    def realizacion(semilla: int):
        rng = np.random.default_rng(semilla)
        cols = rng.integers(0, n_cols, n_cols)
        medias = matriz.to_numpy()[:, cols].mean(axis=1)
        return pd.DataFrame({"decision": nombres, "expected_profit_usd": medias})

    estabilidad = estabilidad_ranking(realizacion, semillas=range(1, 31))

    def con_ruidos(u: float, e: float, r: float):
        sims = simulate_decisions(
            dataset, conversion_model, aov_model,
            n_simulations=400, noise_scales=(u, e, r),
        )
        g = sims.groupby("decision")["incremental_profit_usd"].mean()
        return pd.DataFrame({"decision": g.index, "expected_profit_usd": g.to_numpy()})

    sensibilidad = sensibilidad_ruidos(con_ruidos, factores=(0.5, 1.0, 1.5, 2.0))

    return {
        "valor_informacion": evpi,
        "estabilidad": estabilidad,
        "sensibilidad": sensibilidad,
        "validacion": split_boundary(dataset),
    }


def _lecturas_multirol(top_summary, important_uplift, avanzado) -> dict:
    """Las tres lecturas con modelos independientes.

    Se aisla en su propia función porque depende de servicios externos: si un
    proveedor cae, el resto del payload tiene que seguir construyendose.
    """
    try:
        from agente_multirol import lecturas_multirol

        return lecturas_multirol(_records(top_summary), _records(important_uplift), avanzado)
    except Exception as exc:  # se reporta, no se traga
        return {"lecturas": [], "agregacion": {"modo": "error", "veredicto": str(exc)[:200]}}


def _capa_sql() -> dict[str, Any]:
    """Las consultas de sql/*.sql con su resultado, para enseñarlas en la web.

    La capa SQL existia desde el principio pero no se veía en ningun sitio:
    quien abría la consola no sabía que el análisis descriptivo estaba resuelto
    con DuckDB, CTEs y funciones de ventana. Aquí viaja el texto de cada
    consulta junto a las filas que devuelve, para que se lea una al lado de la
    otra.
    """
    from consultas import (
        CONCENTRACION_DEL_MARGEN,
        CURVA_DE_SATURACION,
        RENTABILIDAD_POR_CANAL,
        concentracion_del_margen,
        curva_de_saturacion,
        rentabilidad_por_canal,
    )

    definidas = [
        {
            "archivo": "sql/02_curva_de_saturacion.sql",
            "titulo": "Curva de saturación publicitaria",
            "proposito": "Al subir de tramo de inversión sube el coste por oportunidad y cae la conversión. Es el hallazgo que decide el caso.",
            "sql": CURVA_DE_SATURACION.strip(),
            "fn": curva_de_saturacion,
        },
        {
            "archivo": "sql/04_concentracion_del_margen.sql",
            "titulo": "Concentración del margen",
            "proposito": "Acumulado por percentil con row_number y sum sobre ventana: cuántas oportunidades pagan de verdad el año.",
            "sql": CONCENTRACION_DEL_MARGEN.strip(),
            "fn": concentracion_del_margen,
        },
        {
            "archivo": "sql/01_rentabilidad_por_canal.sql",
            "titulo": "Rentabilidad por canal",
            "proposito": "De dónde sale el margen y qué canal está comprando volumen caro.",
            "sql": RENTABILIDAD_POR_CANAL.strip(),
            "fn": rentabilidad_por_canal,
        },
    ]

    consultas = []
    for d in definidas:
        try:
            df = d["fn"]()
        except Exception:  # la web no se cae porque falte DuckDB
            continue
        consultas.append(
            {
                "archivo": d["archivo"],
                "titulo": d["titulo"],
                "proposito": d["proposito"],
                "sql": d["sql"],
                "columnas": [str(c) for c in df.columns],
                "filas": _records(df),
            }
        )
    return {"motor": "DuckDB sobre el CSV, sin paso de ingesta", "consultas": consultas}


def _build_payload() -> dict:
    dataset = _read_csv(DATASET_PATH)
    params = _read_csv(PARAMS_PATH)
    summary = _read_csv(SUMMARY_PATH)
    simulations = _read_csv(SIMULATIONS_PATH)

    if not LIVE_DASHBOARD_PATH.exists():
        max_simulation = int(simulations["simulation"].max())
        write_live_dashboard(max_simulation, max_simulation, simulations.to_dict(orient="records"))

    report_text = REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else ""
    report_lines = [line.strip() for line in report_text.splitlines() if line.strip()]

    period_start = str(dataset["date"].min())
    period_end = str(dataset["date"].max())
    converted = dataset[dataset["converted_to_sale"] == 1]
    conversion_model, auc = build_conversion_model(dataset)

    # Mismo corte temporal que usa build_conversion_model. Antes cada archivo
    # rehacía su propio train_test_split con los mismos parámetros: coincidían
    # por casualidad, y bastaba tocar uno para que las métricas pasaran a
    # calcularse sobre datos de entrenamiento sin que nada avisara.
    conversion_train, conversion_test = temporal_split(dataset)
    conversion_scores = conversion_model.predict_proba(conversion_test[FEATURES])[:, 1]
    gain_chart = _build_gain_chart(conversion_test["converted_to_sale"], conversion_scores)

    sold_train, sold_test = temporal_split(converted)
    aov_model = build_aov_model(sold_train)
    aov_pred = np.expm1(aov_model.predict(sold_test[FEATURES]))
    residuals = sold_test["aov_usd"].to_numpy() - aov_pred
    abs_residuals = np.abs(residuals)

    dataset_summary = {
        "rows": int(len(dataset)),
        "period_start": period_start,
        "period_end": period_end,
        "conversion_rate": float(dataset["converted_to_sale"].mean()),
        "ingreso_usd": float(dataset["revenue_usd"].sum()),
        "margen_neto_usd": float(dataset["contribution_profit_usd"].sum()),
        "avg_ticket_usd": float(converted["aov_usd"].mean()),
        "avg_lead_score": float(dataset["lead_score"].mean()),
        "campaign_count": int(dataset[["channel", "campaign_objective"]].drop_duplicates().shape[0]),
        "variable_count": int(len(dataset.columns)),
        "channel_count": int(dataset["channel"].nunique()),
        "segment_count": int(dataset["customer_segment"].nunique()),
        "geography_count": int(dataset["geo_region"].nunique()),
        "objective_count": int(dataset["campaign_objective"].nunique()),
        "coste_medio": float(dataset["cost_attributed_usd"].mean()),
        "inversion_total": float(dataset["cost_attributed_usd"].sum()),
        "roas": float(dataset["revenue_usd"].sum() / dataset["cost_attributed_usd"].sum()),
        "pct_inversion_sobre_ingreso": float(
            dataset["cost_attributed_usd"].sum() / dataset["revenue_usd"].sum()
        ),
        "time_windows": int(dataset["month"].nunique()),
    }

    monthly_summary = (
        dataset.groupby("month")
        .agg(
            ingreso_usd=("revenue_usd", "sum"),
            margen_neto_usd=("contribution_profit_usd", "sum"),
            conversion_rate=("converted_to_sale", "mean"),
        )
        .reset_index()
    )

    important_uplift = params[params["parameter"].isin(UPLIFT_LABELS)].copy()
    important_uplift["label"] = important_uplift["parameter"].map(UPLIFT_LABELS)
    important_uplift["description"] = important_uplift["parameter"].map(UPLIFT_EXPLANATIONS)
    important_uplift["conversion_lift_pct"] = important_uplift["conversion_lift_pct"].fillna(0.0)

    ads_regimes = params[params["parameter"].isin(ADS_LABELS)].copy()
    ads_regimes["label"] = ads_regimes["parameter"].map(ADS_LABELS)

    top_summary = summary.sort_values("ranking").reset_index(drop=True)
    best = top_summary.iloc[0]
    second = top_summary.iloc[1]
    gap_vs_second = float(best["expected_profit_usd"] - second["expected_profit_usd"])
    summary_snapshot_df = (
      top_summary.rename(
        columns={
          "expected_profit_usd": "beneficio_esperado_usd",
          "probability_loss": "probabilidad_perdida",
          "expected_roi": "roi_esperado",
        }
      )[
        [
          "ranking",
          "decisión",
          "beneficio_esperado_usd",
          "p10_usd",
          "p50_usd",
          "p90_usd",
          "probabilidad_perdida",
          "roi_esperado",
        ]
      ]
      .copy()
    )
    # La memo imprime esta columna como porcentaje, así que se convierte aquí:
    # dejarla en fracción hacía que un 17% de riesgo se leyese como 0,2%.
    summary_snapshot_df["probabilidad_perdida"] = (
      summary_snapshot_df["probabilidad_perdida"] * 100
    ).round(1)
    summary_snapshot = summary_snapshot_df.to_json(orient="records", force_ascii=False)

    uplift_snapshot = (
      important_uplift.rename(columns={"conversion_lift_pct": "uplift_conversion_pct"})[
        ["label", "description", "uplift_conversion_pct"]
      ]
      .to_json(orient="records", force_ascii=False)
    )
    agent_memo = build_agent_decision_memo(summary_snapshot, uplift_snapshot)

    executive_notes = []
    capture = False
    for line in report_lines:
        if line.lower().startswith("## lectura ejecutiva"):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture and line.startswith("-"):
            executive_notes.append(line[1:].strip())

    report_checks = [line[1:].strip() for line in report_lines if line.startswith("- dataset") or line.startswith("- parámetros") or line.startswith("- conclusión")]

    recommendation = {
      "headline": agent_memo["headline"],
        "decisión": best["decisión"],
        "expected_profit_usd": float(best["expected_profit_usd"]),
        "expected_roi": float(best["expected_roi"]),
        "probability_loss": float(best["probability_loss"]),
        "gap_vs_second_usd": gap_vs_second,
      "agent_summary": agent_memo["summary"],
      "reasons": agent_memo["reasons"],
      "watchouts": agent_memo["watchouts"],
      "next_actions": agent_memo["next_actions"],
      "switch_signals": agent_memo["switch_signals"],
      "due_diligence": agent_memo["due_diligence"],
      "findings": agent_memo["findings"],
      "tool_trace": agent_memo["tool_trace"],
      "audience_views": agent_memo["audience_views"],
    }

    sample_columns = [
        "date",
        "channel",
        "customer_segment",
        "ad_budget_level",
        "cost_attributed_usd",
        "lead_score",
        "converted_to_sale",
        "revenue_usd",
        "contribution_profit_usd",
    ]
    sample_rows = dataset[sample_columns].head(10).to_dict(orient="records")

    mission_tools = [
        {
            "name": "Tool 01 · Carga de datos",
        "purpose": "Carga la base histórica y valida que el caso tenga cobertura suficiente antes de analizar decisiones.",
        },
        {
        "name": "Tool 02 · Modelo de propensión",
        "purpose": "Estima la probabilidad de éxito de cada oportunidad para priorizar las palancas de crecimiento.",
        },
        {
        "name": "Tool 03 · Modelo de valor esperado",
        "purpose": "Estima el ticket esperado de las oportunidades que convierten, para traducir la conversión en impacto económico.",
        },
        {
        "name": "Tool 04 · Uplift de negocio",
        "purpose": "Compara las cuatro palancas de crecimiento sobre el mismo histórico comercial.",
        },
        {
            "name": "Tool 05 · Monte Carlo",
        "purpose": "Simula 10.000 futuros para ordenar las iniciativas por retorno esperado, dispersión y riesgo de pérdida.",
        },
    ]

    avanzado = _analisis_avanzado(
        simulations, summary, dataset, conversion_model, aov_model
    )

    return {
      "title": f"{OPERADOR} · Presupuesto bajo atribución rota",
      "subtitle": (
          f"Consola de decisión para la {UNIDAD} de {OPERADOR}: aprende del histórico, "
          "estima que aporta cada palanca y simula 10.000 futuros antes de comprometer "
          "el presupuesto del trimestre."
      ),
        "stages": STAGES,
        "tools": mission_tools,
        "dataset": {
            "summary": dataset_summary,
        "monthly": _records(monthly_summary),
            "sample": sample_rows,
        },
      "models": {
        "classification": {
          "name": "Regresión logística",
          "purpose": "Calcula la probabilidad de éxito de cada oportunidad a partir del canal, el segmento, el contexto comercial y las señales de calidad.",
          "auc": float(auc),
          "positive_rate": float(conversion_test["converted_to_sale"].mean()),
          "avg_predicted_prob": float(conversion_scores.mean()),
          "gain_chart": gain_chart,
        },
        "regressión": {
          "name": "Gradient Boosting Regressor",
          "purpose": "Estima el ticket esperado de la oportunidad para traducir la conversión en dólares.",
          "mae_usd": float(mean_absolute_error(sold_test["aov_usd"], aov_pred)),
          "r2": float(r2_score(sold_test["aov_usd"], aov_pred)),
          "mean_residual_usd": float(residuals.mean()),
          "p90_abs_error_usd": float(np.percentile(abs_residuals, 90)),
          "residual_bands": _build_residual_bands(residuals),
        },
      },
        "uplift": {
        "main": _records(important_uplift),
        "ads": _records(ads_regimes),
        },
        "simulation": {
        "summary": _records(top_summary),
          "total_simulations": int(simulations["simulation"].max()),
          "live_dashboard": f"dashboards/{LIVE_DASHBOARD_PATH.name}",
        "recent": _records(simulations.sort_values("simulation").tail(24)),
        },
        "recommendation": recommendation,
        "report": {
            "checks": report_checks,
            "executive_notes": executive_notes,
        },
        "avanzado": avanzado,
        "sql": _capa_sql(),
        "multirol": _lecturas_multirol(top_summary, important_uplift, avanzado),
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nordika · Consola de decisión</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      /* paleta clara editorial, inspirada en legend.xyz (ver diseno/03_referencias.md) */
      --bg: #ededed;
      --bg-deep: #ededed;
      --bg-soft: #f2f2f2;
      --panel: #f2f2f2;
      --panel-strong: #faf9f5;
      --line: #dedddc;
      --text: #131313;
      --muted: #6c6c6c;
      --faint: #949494;
      --ghost: #b2b2b2;
      --accent: #d9531e;
      --accent2: #1fa971;
      --amber: #d9531e;
      --pink: #7c3aed;
      --red: #d9531e;
      --blue: #2f80ed;
      --ink: #131313;
      --ink-soft: #2d2d2d;
      --on-ink: #ffffff;
      --shadow: 0 12px 32px rgba(19, 19, 19, 0.08);
      --glow: none;
      --font-display: "IBM Plex Mono", "SFMono-Regular", Menlo, monospace;
      --font-text: "Inter", -apple-system, "Segoe UI", sans-serif;
    }
    /* rotación de acento por fase, tomada del hero rotativo de legend.xyz */
    [data-phase-accent="briefing"] { --phase-accent: var(--accent); }
    [data-phase-accent="ingesta"] { --phase-accent: var(--blue); }
    [data-phase-accent="uplift"] { --phase-accent: var(--pink); }
    [data-phase-accent="montecarlo"] { --phase-accent: var(--accent2); }
    [data-phase-accent="reporte"] { --phase-accent: var(--accent); }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--text);
      background: var(--bg-deep);
      font-family: var(--font-text);
      min-height: 100vh;
      position: relative;
    }
    /* grid editorial de 3 columnas con divisores 1px, la firma visual de
       legend.xyz: sensación de papel cuadriculado detras de todo el contenido */
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
      background-image:
        repeating-linear-gradient(180deg, var(--line) 0 5px, transparent 5px 11px),
        repeating-linear-gradient(180deg, var(--line) 0 5px, transparent 5px 11px),
        repeating-linear-gradient(180deg, var(--line) 0 5px, transparent 5px 11px);
      background-size: 1px 100%, 1px 100%, 1px 100%;
      background-position: 25% 0, 50% 0, 75% 0;
      background-repeat: no-repeat;
      opacity: 0.85;
    }
    /* barra sticky de estado, patron de la barra de anuncio de legend.xyz */
    .topbar {
      position: sticky;
      top: 0;
      z-index: 40;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 11px 20px;
      background: var(--panel-strong);
      border-bottom: 1px solid var(--line);
      font-family: var(--font-display);
      font-size: 11.5px;
      letter-spacing: 0.06em;
      color: var(--muted);
    }
    .topbar-left { display: flex; align-items: center; gap: 9px; min-width: 0; }
    .topbar-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--phase-accent, var(--accent));
      flex: none;
      transition: background 0.4s ease;
    }
    .topbar-msg { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .topbar-right { text-transform: uppercase; letter-spacing: 0.14em; color: var(--muted); white-space: nowrap; }
    @media (max-width: 640px) { .topbar-right { display: none; } }
    .shell {
      width: min(1660px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 40px 0 64px;
      position: relative;
      z-index: 1;
    }
    .hero, .panel, .metric, .tool-card, .stage-button, .console, .table-wrap {
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      border-radius: 24px;
    }
    .hero {
      padding: clamp(28px, 4vw, 52px);
      position: relative;
      overflow: hidden;
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 28px;
    }
    .hero-copy, .hero-status { position: relative; z-index: 1; }
    h1, .verdict, .panel-title, .stage-title, .metric-value, .status-big {
      font-family: var(--font-text);
      font-weight: 500;
      letter-spacing: -0.025em;
    }
    /* etiquetas tecnicas: único lugar donde vive la mono, como legend.xyz */
    .eyebrow, .stage-index, .hero-coord, .ticker-item, .topbar,
    .metric-label, .hud-chip-label, .footer-meta, .status-chip {
      font-family: var(--font-display);
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
    }
    h1 {
      margin: 14px 0 8px;
      font-size: clamp(38px, 5vw, 68px);
      line-height: 1.04;
      letter-spacing: -0.03em;
      text-wrap: balance;
      font-weight: 500;
    }
    /* titular a dos tonos: la segunda mitad en gris fantasma, firma de legend */
    .ghost-line { color: var(--ghost); }
    .hero p {
      max-width: 760px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.6;
      margin: 0;
    }
    /* hero rotativo: palabra + acento cambian juntos cada ~3s, como legend.xyz */
    .hero p.hero-rotator {
      margin-top: 16px;
      max-width: none;
      font-family: var(--font-display);
      font-size: clamp(18px, 2.2vw, 24px);
      font-weight: 600;
    }
    .hero p.hero-rotator .hero-rotator-word {
      color: var(--phase-accent, var(--accent));
      transition: color 0.4s ease;
    }
    .hero p.hero-rotator .hero-rotator-rest {
      color: var(--text);
    }
    .hero-coord {
      position: absolute;
      top: 20px;
      font-family: var(--font-display);
      font-size: 11px;
      letter-spacing: 0.08em;
      color: var(--ghost);
      z-index: 1;
    }
    .hero-coord-left { left: 24px; }
    .hero-coord-right { right: 24px; }
    @media (max-width: 640px) {
      .hero-coord { display: none; }
    }
    /* footer oscuro con resplandor radial detras del logo, como legend.xyz */
    .site-footer {
      color: #d9d9d9;
      margin-top: 56px;
      border-radius: 24px;
      background: var(--ink);
      padding: 72px 28px 56px;
      position: relative;
      overflow: hidden;
      display: grid;
      place-items: center;
      text-align: center;
    }
    .footer-glow {
      position: absolute;
      top: 22%;
      left: 50%;
      transform: translateX(-50%);
      width: min(560px, 90%);
      aspect-ratio: 1;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.16), transparent 62%);
      pointer-events: none;
    }
    .footer-mark {
      position: relative;
      width: 66px;
      height: 66px;
      border-radius: 50%;
      background: radial-gradient(circle at 42% 34%, #ffffff, #c9c9c9 52%, #6f6f6f 100%);
      box-shadow: 0 0 60px rgba(255,255,255,0.28);
      margin-bottom: 22px;
    }
    .footer-meta {
      position: relative;
      font-family: var(--font-display);
      font-size: 11.5px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #8f8f8f;
    }
    /* ticker de métricas reales, mismo patron que el marquee de logos de
       partners de legend.xyz, pero con datos del caso en vez de logos */
    .ticker {
      margin-top: 18px;
      overflow: hidden;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 10px 0;
      -webkit-mask-image: linear-gradient(90deg, transparent, black 8%, black 92%, transparent);
      mask-image: linear-gradient(90deg, transparent, black 8%, black 92%, transparent);
    }
    .ticker-track {
      display: flex;
      width: max-content;
      gap: 48px;
      animation: ticker-scroll 28s linear infinite;
    }
    .ticker-item {
      font-family: var(--font-display);
      font-size: 12px;
      letter-spacing: 0.06em;
      color: var(--muted);
      white-space: nowrap;
    }
    .ticker-item strong { color: var(--text); }
    @keyframes ticker-scroll {
      from { transform: translateX(0); }
      to { transform: translateX(-50%); }
    }
    @media (prefers-reduced-motion: reduce) {
      .ticker-track { animation: none; }
    }
    .hero-grid {
      margin-top: 22px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      padding: 16px;
      min-height: 110px;
      position: relative;
      overflow: hidden;
    }
    .metric::after {
      content: "";
      position: absolute;
      inset: auto 0 0 0;
      height: 3px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      box-shadow: 0 0 20px rgba(217, 142, 74, 0.45);
    }
    .metric-label {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      color: var(--muted);
    }
    .metric-value {
      margin-top: 10px;
      font-size: 28px;
      font-weight: 700;
      color: var(--text);
    }
    .hero-status {
      display: grid;
      gap: 16px;
      align-content: stretch;
    }
    .mission-hud {
      border: 1px solid var(--line);
      background: var(--panel-strong);
      border-radius: 24px;
      box-shadow: var(--shadow), var(--glow);
      padding: 18px;
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 18px;
      position: relative;
      overflow: hidden;
    }
    .mission-hud::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 28%, transparent 72%, rgba(217,142,74,0.05));
      pointer-events: none;
    }
    .status-orbit {
      width: 100%;
    }
    .status-ring {
      width: 100%;
      border-radius: 12px;
      position: relative;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-left: 3px solid var(--accent);
      padding: 20px 22px;
    }
    .status-core {
      position: relative;
      z-index: 1;
      text-align: left;
    }
    .status-big {
      font-size: 24px;
      line-height: 1.2;
      margin-top: 6px;
      color: var(--text);
      letter-spacing: -0.01em;
    }
    .status-sub {
      margin-top: 8px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
    }
    .status-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      align-content: center;
    }
    .hud-chip {
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel-strong);
      padding: 14px 16px;
      min-height: 88px;
    }
    .hud-chip-label {
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .hud-chip-value {
      margin-top: 10px;
      font-size: 21px;
      line-height: 1.1;
      color: var(--text);
    }
    .hud-chip-copy {
      margin-top: 8px;
      color: var(--faint);
      font-size: 12px;
      line-height: 1.45;
    }
    .console {
      /* bloque oscuro deliberado, sección "core actions" al estilo legend.xyz:
         contraste editorial claro/oscuro, no es un accidente de tema */
      padding: 18px;
      min-height: 220px;
      position: relative;
      overflow: hidden;
      background: var(--ink) !important;
      border-color: var(--ink) !important;
      color: #d9d9d9;
    }
    .console::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(255,255,255,0.04), transparent 35%, transparent 70%, rgba(217,83,30,0.08));
      pointer-events: none;
    }
    .console-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      font-size: 12px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #9a9a9a;
    }
    .console-head-right {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .console-command {
      color: var(--accent);
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
    }
    .console-log {
      display: grid;
      gap: 10px;
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      color: #d9d9d9;
    }
    .progress-shell {
      margin-top: 18px;
      height: 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--line);
      overflow: hidden;
    }
    .progress-fill {
      width: 0%;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent2), var(--amber));
      box-shadow: 0 0 24px rgba(217,142,74,0.35);
      transition: width 0.18s linear;
    }
    .toolbar {
      margin-top: 18px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    /* pastilla ghost/outline (secundario), como pide la guía legend.xyz */
    .action {
      border: 1px solid var(--line);
      background: transparent;
      color: var(--text);
      border-radius: 999px;
      padding: 12px 16px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 11px;
      cursor: pointer;
      transition: transform 0.2s ease, border-color 0.2s ease, opacity 0.2s ease, background 0.2s ease;
    }
    .action:hover:not(:disabled) {
      transform: translateY(-1px);
      border-color: var(--ink);
    }
    .action:disabled {
      opacity: 0.45;
      cursor: wait;
    }
    /* pastilla negra solida (primario), como pide la guía legend.xyz */
    .action-primary {
      background: var(--ink);
      border-color: var(--ink);
      color: var(--on-ink);
    }
    .action-primary:hover:not(:disabled) {
      background: var(--ink-soft);
      border-color: var(--ink-soft);
    }
    .action-warn {
      border-color: var(--accent);
      color: var(--accent);
    }
    .action-warn:hover:not(:disabled) {
      background: var(--accent);
      color: var(--on-ink);
    }
    .layout {
      margin-top: 40px;
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 40px;
    }
    .rail {
      display: grid;
      gap: 22px;
      align-content: start;
      position: sticky;
      top: 20px;
      height: max-content;
    }
    #stage-buttons {
      display: grid;
      gap: 18px;
    }
    .stage-button, .tool-card, .panel, .table-wrap {
      padding: 18px;
    }
    /* icono circular de color por fase, patron "core actions" de legend.xyz */
    .phase-icon {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: var(--icon-bg);
      display: grid;
      place-items: center;
      margin-bottom: 10px;
      transition: transform 0.28s cubic-bezier(0.16,1,0.3,1);
    }
    .phase-icon svg { width: 17px; height: 17px; color: #fff; }
    .stage-button:hover .phase-icon { transform: scale(1.09) rotate(-4deg); }
    .stage-button.active .phase-icon { transform: scale(1.06); }

    /* corner brackets: marcas en L en las esquinas, detalle editorial de legend */
    .panel { position: relative; }
    .panel::before, .panel::after {
      content: "";
      position: absolute;
      width: 14px; height: 14px;
      border: 1px solid var(--ghost);
      opacity: 0;
      transition: opacity 0.3s ease;
      pointer-events: none;
    }
    .panel::before { top: 10px; left: 10px; border-right: none; border-bottom: none; }
    .panel::after { bottom: 10px; right: 10px; border-left: none; border-top: none; }
    .panel:hover::before, .panel:hover::after { opacity: 0.65; }

    /* entrada escalonada de las tarjetas al cambiar de fase */
    .stage-pane.active > * { animation: rise-in 0.5s cubic-bezier(0.16,1,0.3,1) backwards; }
    .stage-pane.active > *:nth-child(1) { animation-delay: 0.02s; }
    .stage-pane.active > *:nth-child(2) { animation-delay: 0.09s; }
    .stage-pane.active > *:nth-child(3) { animation-delay: 0.16s; }
    .stage-pane.active > *:nth-child(4) { animation-delay: 0.23s; }
    @keyframes rise-in {
      from { opacity: 0; transform: translateY(14px); }
      to { opacity: 1; transform: none; }
    }
    @media (prefers-reduced-motion: reduce) {
      .stage-pane.active > * { animation: none; }
      .phase-icon { transition: none; }
    }

    /* bloque de feature numerado, patron "01 Cash in, cash out" de legend.xyz */
    .stage-button {
      color: var(--text);
      font-family: inherit;
      cursor: pointer;
      transition: transform 0.22s cubic-bezier(0.16,1,0.3,1), border-color 0.22s ease, box-shadow 0.22s ease;
      position: relative;
      overflow: hidden;
      display: grid;
      grid-template-columns: 30px 1fr;
      gap: 14px;
      align-items: start;
      text-align: left;
      padding: 22px 20px;
    }
    .stage-index {
      font-family: var(--font-display);
      font-size: 11px;
      letter-spacing: 0.06em;
      color: var(--ghost);
      padding-top: 4px;
      transition: color 0.22s ease;
    }
    .stage-button.active .stage-index { color: var(--phase-accent, var(--accent)); }
    .stage-body { display: grid; gap: 6px; min-width: 0; }
    .stage-button::after {
      content: "";
      position: absolute;
      inset: auto 0 0 0;
      height: 2px;
      background: transparent;
      transition: background 0.22s ease;
    }
    .stage-button:hover, .stage-button.active {
      transform: translateY(-2px);
      border-color: var(--ink);
      box-shadow: 0 10px 26px rgba(19,19,19,0.10);
    }
    .stage-button.active::after {
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      box-shadow: 0 0 24px rgba(217,142,74,0.4);
    }
    .stage-button.running::after {
      background: linear-gradient(90deg, var(--amber), var(--accent));
      box-shadow: 0 0 24px rgba(224,179,77,0.35);
    }
    .stage-button.done::after {
      background: linear-gradient(90deg, var(--accent2), var(--accent));
      box-shadow: 0 0 24px rgba(127,174,142,0.30);
    }
    .stage-button.locked {
      opacity: 0.45;
      filter: grayscale(0.5);
    }
    .stage-button.locked:hover {
      transform: none;
      border-color: inherit;
      box-shadow: none;
    }
    .stage-title {
      display: block;
      font-size: 18px;
      line-height: 1.25;
      color: var(--text);
      letter-spacing: -0.01em;
    }
    .stage-copy {
      display: block;
      color: var(--muted);
      line-height: 1.5;
      font-size: 14px;
    }
    .main {
      display: grid;
      gap: 22px;
    }
    .stage-pane {
      display: none;
      gap: 32px;
    }
    .stage-pane.active {
      display: grid;
      animation: fadeIn 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @media (prefers-reduced-motion: reduce) {
      .stage-pane.active { animation: none; }
      .placeholder-ring { animation: none; border-top-color: rgba(217, 142, 74, 0.4); }
    }
    .briefing-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 22px;
      align-items: start;
      min-height: 100%;
    }
    .briefing-stack {
      display: grid;
      gap: 22px;
      align-content: start;
    }
    .panel-title {
      margin: 0 0 6px;
      font-size: 20px;
      color: var(--text);
    }
    .panel-copy {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .kpi-grid, .insight-grid, .summary-grid, .report-grid, .model-grid, .tech-grid, .montecarlo-grid {
      display: grid;
      gap: 14px;
    }
    .kpi-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .summary-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .insight-grid, .report-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .model-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .tech-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .montecarlo-grid { grid-template-columns: 1fr; }
    .tool-name {
      font-size: 16px;
      color: var(--text);
      margin: 8px 0;
    }
    .tool-card {
      position: relative;
      overflow: hidden;
    }
    .tool-purpose {
      color: var(--muted);
      line-height: 1.55;
      font-size: 14px;
    }
    .bars, .uplift-cards, .summary-cards {
      display: grid;
      gap: 12px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: 220px 1fr 110px;
      gap: 12px;
      align-items: center;
    }
    .bar-track {
      height: 18px;
      border-radius: 999px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(196, 188, 172, 0.12);
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
      position: relative;
    }
    .bar-fill.red { background: linear-gradient(90deg, var(--red), #ff9c7a); }
    .bar-fill.amber { background: linear-gradient(90deg, var(--amber), #ffef99); }
    .line-shell {
      height: 280px;
      position: relative;
      border-radius: 18px;
      background: var(--panel-strong);
      border: 1px solid rgba(196, 188, 172, 0.14);
      overflow: hidden;
    }
    .line-shell svg { width: 100%; height: 100%; display: block; }
    .mini-chart {
      height: 240px;
      border-radius: 18px;
      background: var(--panel-strong);
      border: 1px solid rgba(196, 188, 172, 0.14);
      overflow: hidden;
    }
    .mini-chart svg { width: 100%; height: 100%; display: block; }
    .table-wrap {
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }
    th, td {
      padding: 12px 10px;
      text-align: left;
      border-bottom: 1px solid rgba(196, 188, 172, 0.10);
      font-size: 13px;
    }
    th {
      text-transform: uppercase;
      letter-spacing: 0.15em;
      font-size: 11px;
      color: var(--muted);
      position: sticky;
      top: 0;
      background: var(--panel-strong);
    }
    .iframe-shell {
      position: relative;
      border-radius: 22px;
      overflow: hidden;
      border: 1px solid rgba(196, 188, 172, 0.16);
      background: #101014;
      min-height: 1040px;
      box-shadow: inset 0 0 80px rgba(217,142,74,0.08);
    }
    .montecarlo-placeholder {
      position: absolute;
      inset: 18px;
      z-index: 3;
      display: none;
      place-items: center;
      border-radius: 18px;
      border: 1px solid rgba(196, 188, 172, 0.18);
      background: var(--panel-strong);
      padding: 28px;
      text-align: center;
    }
    .montecarlo-placeholder.is-visible {
      display: grid;
    }
    .placeholder-ring {
      width: 124px;
      height: 124px;
      border-radius: 50%;
      border: 2px solid rgba(196, 188, 172, 0.16);
      border-top-color: var(--accent);
      box-shadow: 0 0 32px rgba(217,142,74,0.16);
      animation: rotate 1.2s linear infinite;
      margin: 0 auto 18px;
    }
    .placeholder-title {
      font-size: 24px;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .placeholder-copy {
      margin-top: 10px;
      max-width: 520px;
      color: #9c968c;
      line-height: 1.7;
    }
    .wait-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(2, 7, 13, 0.72);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      display: none;
      place-items: center;
      z-index: 60;
      padding: 24px;
    }
    .wait-modal-overlay.is-visible {
      display: grid;
      animation: fadeIn 0.18s ease-out;
    }
    .wait-modal {
      width: min(440px, 100%);
      border-radius: 20px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      box-shadow: 0 40px 120px rgba(19,19,19,0.18);
      padding: 36px 30px 28px;
      text-align: center;
      position: relative;
    }
    /* corner brackets, detalle editorial de legend.xyz (marcas en L) */
    .wait-modal::before,
    .wait-modal::after {
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      border: 2px solid var(--accent);
      opacity: 0.7;
      pointer-events: none;
    }
    .wait-modal::before {
      top: -1px;
      left: -1px;
      border-right: none;
      border-bottom: none;
      border-radius: 6px 0 0 0;
    }
    .wait-modal::after {
      bottom: -1px;
      right: -1px;
      border-left: none;
      border-top: none;
      border-radius: 0 0 6px 0;
    }
    .wait-modal .placeholder-ring {
      width: 84px;
      height: 84px;
      margin-bottom: 18px;
    }
    .wait-modal-title {
      font-size: 19px;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .wait-modal-copy {
      margin-top: 10px;
      color: #9c968c;
      font-size: 14px;
      line-height: 1.6;
    }
    .wait-modal-progress {
      margin-top: 22px;
    }
    .wait-modal-pct {
      font-variant-numeric: tabular-nums;
      font-size: 32px;
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 10px;
    }
    .wait-modal-actions {
      margin-top: 26px;
      display: flex;
      gap: 10px;
      justify-content: center;
    }
    @media (prefers-reduced-motion: reduce) {
      .wait-modal .placeholder-ring { animation: none; border-top-color: rgba(196, 188, 172, 0.16); }
      .wait-modal-overlay.is-visible { animation: none; }
    }
    .iframe-shell::before {
      content: "";
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle, rgba(25,230,255,.06) 0 1px, transparent 1px),
        linear-gradient(90deg, rgba(25,230,255,.05) 1px, transparent 1px),
        linear-gradient(180deg, rgba(25,230,255,.05) 1px, transparent 1px);
      background-size: 28px 28px, 28px 28px, 28px 28px;
      mask-image: radial-gradient(circle at center, black 30%, transparent 86%);
      opacity: 0.85;
      pointer-events: none;
      z-index: 1;
    }
    .iframe-shell::after {
      content: "";
      position: absolute;
      inset: 22px;
      border-radius: 50%;
      background: conic-gradient(from 0deg, rgba(127,174,142,.18), transparent 52deg, transparent 360deg);
      filter: blur(2px);
      mix-blend-mode: screen;
      animation: rotate 6s linear infinite;
      opacity: 0.55;
      pointer-events: none;
      z-index: 1;
    }
    iframe {
      position: relative;
      z-index: 2;
      width: 100%;
      min-height: 1040px;
      border: 0;
      background: #101014;
      overflow: hidden;
    }
    .panel-radar {
      background: var(--panel);
    }
    .panel-hud {
      background: var(--panel);
    }
    .bullet-list {
      margin: 14px 0 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.7;
    }
    .audience-switch {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 18px 0 10px;
    }
    .audience-chip {
      min-width: 132px;
      border: 1px solid rgba(196, 188, 172, 0.22);
      background: var(--panel-strong);
      color: var(--text);
      padding: 12px 16px;
      border-radius: 16px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      cursor: pointer;
      transition: transform 0.2s ease, border-color 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
    }
    .audience-chip.active {
      color: #1a1408;
      background: linear-gradient(135deg, #7fae8e, #d98e4a);
      border-color: transparent;
      box-shadow: 0 12px 30px rgba(127, 174, 142, 0.24);
    }
    .audience-chip:hover {
      transform: translateY(-1px);
    }
    .audience-caption {
      color: #d98e4a;
      font-size: 11px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin-top: 4px;
    }
    .audience-summary {
      color: var(--muted);
      margin-top: 4px;
      line-height: 1.6;
    }
    .trace-list {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }
    .trace-item {
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
    }
    .trace-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
    }
    .trace-name {
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
      letter-spacing: 0.04em;
    }
    .trace-args {
      color: var(--accent);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .trace-purpose {
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 6px;
    }
    .trace-outcome {
      color: var(--muted);
      line-height: 1.6;
      font-size: 14px;
    }
    .tag-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
      background: var(--panel-strong);
    }
    .status-chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
      background: var(--panel-strong);
    }
    .status-chip.ready {
      border-color: rgba(31, 169, 113, 0.35);
      color: #157a52;
    }
    .status-chip.running {
      border-color: rgba(217, 83, 30, 0.35);
      color: #a53f16;
    }
    .status-chip.alert {
      border-color: rgba(217, 83, 30, 0.5);
      color: #a53f16;
      background: rgba(217, 83, 30, 0.08);
    }
    .verdict {
      font-size: clamp(28px, 3vw, 42px);
      line-height: 1.05;
      margin: 6px 0 12px;
      text-transform: uppercase;
      color: var(--text);
    }
    .flash {
      animation: flash 0.4s ease;
    }
    @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    @keyframes scan { from { transform: translateY(-4px); } to { transform: translateY(4px); } }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes flash {
      0% { box-shadow: 0 0 0 1px rgba(217,142,74,0.15), 0 24px 80px rgba(0,0,0,0.35); }
      50% { box-shadow: 0 0 0 1px rgba(217,142,74,0.35), 0 0 40px rgba(217,142,74,0.20), 0 24px 80px rgba(0,0,0,0.35); }
      100% { box-shadow: 0 0 0 1px rgba(217,142,74,0.15), 0 24px 80px rgba(0,0,0,0.35); }
    }
    @media (max-width: 1200px) {
      .hero, .layout, .insight-grid, .report-grid, .model-grid, .mission-hud, .briefing-grid { grid-template-columns: 1fr; }
      .kpi-grid, .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .tech-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .rail { position: static; }
    }
    @media (max-width: 760px) {
      .shell { width: min(100vw - 16px, 100%); padding-top: 16px; }
      .hero-grid, .kpi-grid, .summary-grid, .tech-grid { grid-template-columns: 1fr; }
      .bar-row { grid-template-columns: 1fr; }
      .status-grid { grid-template-columns: 1fr; }
      .stage-button, .tool-card, .panel, .table-wrap, .console { padding: 16px; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-left">
      <span class="topbar-dot"></span>
      <span class="topbar-msg" id="topbar-msg">Consola lista para recorrer el caso completo.</span>
    </div>
    <div class="topbar-right" id="topbar-right">Decision Intelligence</div>
  </div>
  <div class="shell">
    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow">Consola ejecutiva</div>
        <h1 id="hero-title"></h1>
        <p id="hero-subtitle"></p>
        <p class="hero-rotator">
          <span id="hero-rotator-word" class="hero-rotator-word"></span>
          <span id="hero-rotator-rest" class="hero-rotator-rest"></span>
        </p>
        <div class="hero-grid" id="hero-kpis"></div>
        <div class="hero-coord hero-coord-left" id="hero-coord-left"></div>
        <div class="hero-coord hero-coord-right" id="hero-coord-right"></div>
      </div>
      <div class="hero-status">
        <section class="mission-hud">
          <div class="status-orbit">
            <div class="status-ring">
              <div class="status-core">
                <div class="eyebrow" id="hud-active-stage">Fase 01</div>
                <div class="status-big" id="hud-active-title">Introduccion</div>
                <div class="status-sub" id="hud-active-copy">Consola lista para recorrer el caso completo.</div>
              </div>
            </div>
          </div>
          <div class="status-grid">
            <article class="hud-chip">
              <div class="hud-chip-label">Runtime</div>
              <div class="hud-chip-value" id="hud-runtime">Modo local</div>
              <div class="hud-chip-copy">Estado del backend y de la sincronizacion de etapas.</div>
            </article>
            <article class="hud-chip">
              <div class="hud-chip-label">Estado live</div>
              <div class="hud-chip-value" id="hud-live">Sin backend</div>
              <div class="hud-chip-copy">Situacion actual del panel Monte Carlo en tiempo real.</div>
            </article>
            <article class="hud-chip">
              <div class="hud-chip-label">Cobertura</div>
              <div class="hud-chip-value">5 fases</div>
              <div class="hud-chip-copy">De exploracion inicial a recomendacion priorizada.</div>
            </article>
            <article class="hud-chip">
              <div class="hud-chip-label">Simulacion</div>
              <div class="hud-chip-value">10.000 futuros</div>
              <div class="hud-chip-copy">Exploracion de retorno esperado, dispersion y riesgo de perdida.</div>
            </article>
          </div>
        </section>
      </div>
    </section>

    <div class="ticker" aria-hidden="true">
      <div class="ticker-track" id="ticker-track"></div>
    </div>

    <section class="layout">
      <aside class="rail">
        <div id="stage-buttons"></div>
      </aside>

      <main class="main">
        <section class="stage-pane" id="pane-briefing">
          <div class="briefing-grid">
            <div class="briefing-stack">
              <section class="panel">
                <div class="eyebrow">Vision general</div>
                <h2 class="panel-title">Una sola interfaz para recorrer todo el caso</h2>
                <p class="panel-copy">La aplicacion articula un flujo completo para analizar la base historica, estimar el comportamiento esperado, cuantificar el uplift de cada palanca, simular miles de escenarios y cerrar con una recomendacion priorizada.</p>
                <div class="tag-row" id="briefing-tags"></div>
              </section>
              <section class="console" id="console-panel">
              <div class="console-head">
                <span>Estado operativo</span>
                <div class="console-head-right">
                  <span class="status-chip" id="console-runtime-badge">Modo local</span>
                  <span class="status-chip" id="console-live-badge">Sin backend</span>
                  <span id="console-stage-label"></span>
                </div>
              </div>
              <div class="console-command" id="console-command"></div>
              <div class="console-log" id="console-log"></div>
              <div class="progress-shell"><div class="progress-fill" id="progress-fill"></div></div>
              <div class="toolbar">
                <button class="action" id="autoplay-btn">Secuencia automatica</button>
                <button class="action" id="reset-btn">Volver al briefing</button>
              </div>
              </section>
            </div>
          </div>
        </section>

        <section class="stage-pane" id="pane-ingesta">
          <div class="kpi-grid" id="dataset-kpis"></div>
          <div class="insight-grid">
            <section class="panel">
              <div class="eyebrow">Cobertura del caso</div>
              <h2 class="panel-title">Que informacion tiene disponible el agente</h2>
              <p class="panel-copy">Antes de modelizar conviene comprobar que el historico cubre suficiente variedad de condiciones: canales, campañas, segmentos, geografias y ventana temporal.</p>
              <div class="kpi-grid" id="dataset-structure-cards"></div>
            </section>
            <section class="panel">
              <div class="eyebrow">Serie temporal</div>
              <h2 class="panel-title">Evolucion mensual del negocio</h2>
              <p class="panel-copy">La serie de revenue y beneficio de contribucion da contexto sobre la estabilidad del negocio antes de evaluar nuevas palancas.</p>
              <div class="line-shell"><svg id="monthly-chart" viewBox="0 0 680 280" preserveAspectRatio="none"></svg></div>
            </section>
          </div>
          <section class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Canal</th>
                  <th>Segmento</th>
                  <th>Nivel de inversion</th>
                  <th>Lead score</th>
                  <th>Conversion</th>
                  <th>Revenue</th>
                  <th>Beneficio contribucion</th>
                </tr>
              </thead>
              <tbody id="sample-table"></tbody>
            </table>
          </section>
        </section>

        <section class="stage-pane" id="pane-uplift">
          <div class="model-grid">
            <section class="panel">
              <div class="eyebrow">Modelo 01</div>
              <h2 class="panel-title">Regresion logistica para probabilidad de exito</h2>
              <p class="panel-copy">Este modelo estima la probabilidad de cierre de cada oportunidad usando señales de canal, segmento, calidad del lead y contexto comercial.</p>
              <div class="tech-grid" id="classification-kpis"></div>
              <div class="mini-chart" style="margin-top:14px"><svg id="gain-chart" viewBox="0 0 680 240" preserveAspectRatio="none"></svg></div>
            </section>
            <section class="panel">
              <div class="eyebrow">Modelo 02</div>
              <h2 class="panel-title">Gradient boosting para valor esperado</h2>
              <p class="panel-copy">Este modelo estima el valor economico de las oportunidades que convierten y ayuda a traducir propension en impacto monetario.</p>
              <div class="tech-grid" id="regression-kpis"></div>
              <div class="bars" id="residual-bars" style="margin-top:14px"></div>
            </section>
          </div>
          <section class="panel">
            <div class="eyebrow">Palancas de negocio</div>
            <h2 class="panel-title">Escenarios con mayor uplift esperado</h2>
            <p class="panel-copy">Aqui se muestran las iniciativas mejor posicionadas segun el analisis contrafactual: cuanto mejoran la conversion y cuanto valor añaden por oportunidad.</p>
            <div class="uplift-cards" id="uplift-cards"></div>
          </section>
        </section>

        <section class="stage-pane" id="pane-montecarlo">
          <div class="montecarlo-grid">
            <section class="panel">
              <div class="eyebrow">Simulacion en directo</div>
              <h2 class="panel-title">Panel live de Monte Carlo</h2>
              <p class="panel-copy">El radar, la telemetria y el ranking evolucionan en tiempo real mientras el agente recorre 10.000 escenarios posibles para cada decision.</p>
              <button class="action action-warn" id="relanzar-montecarlo-btn">Relanzar simulacion desde 0%</button>
              <div class="iframe-shell">
                <div class="montecarlo-placeholder" id="montecarlo-placeholder">
                  <div>
                    <div class="placeholder-ring"></div>
                    <div class="placeholder-title" id="montecarlo-placeholder-title">Precalculando simulacion</div>
                    <div class="placeholder-copy" id="montecarlo-placeholder-copy">El backend está preparando los elementos previos al lanzamiento. El dashboard live se mostrará en cuanto arranque la simulación real.</div>
                  </div>
                </div>
                <iframe id="live-frame" title="Monte Carlo live"></iframe>
              </div>
            </section>
          </div>
          <section class="panel panel-radar">
            <div class="eyebrow">Lectura consolidada</div>
            <h2 class="panel-title">Ranking final de alternativas</h2>
            <p class="panel-copy">La comparativa final resume retorno esperado, dispersión y riesgo de perdida para que la conclusion sea inmediata.</p>
            <div class="summary-cards" id="summary-cards"></div>
          </section>
        </section>

        <section class="stage-pane" id="pane-reporte">
          <div class="report-grid">
            <section class="panel">
              <div class="eyebrow">Recomendacion final</div>
              <div class="audience-caption">Selecciona enfoque de lectura</div>
              <div class="audience-switch" id="audience-switch">
                <button class="audience-chip active" data-audience="ceo">Finanzas</button>
                <button class="audience-chip" data-audience="growth">Operacion</button>
                <button class="audience-chip" data-audience="riesgo">Riesgo</button>
              </div>
              <div class="audience-summary" id="audience-summary"></div>
              <div class="verdict" id="verdict-headline"></div>
              <p class="panel-copy" id="verdict-copy"></p>
              <ul class="bullet-list" id="reason-list"></ul>
            </section>
            <section class="panel">
              <div class="eyebrow">Riesgos y siguientes pasos</div>
              <h2 class="panel-title">Puntos de control para la decision</h2>
              <ul class="bullet-list" id="watchouts-list"></ul>
              <div class="tag-row" id="report-checks"></div>
            </section>
          </div>
          <div class="report-grid">
            <section class="panel">
              <div class="eyebrow">Consultas realizadas</div>
              <h2 class="panel-title">Huella de herramientas</h2>
              <div class="trace-list" id="tool-trace"></div>
            </section>
            <section class="panel">
              <div class="eyebrow">Hallazgos adicionales</div>
              <h2 class="panel-title">Lecturas complementarias</h2>
              <ul class="bullet-list" id="agent-findings"></ul>
            </section>
          </div>
          <div class="report-grid">
            <section class="panel">
              <div class="eyebrow">Cuando cambiaria la recomendacion</div>
              <h2 class="panel-title">Senales para rotar la apuesta</h2>
              <ul class="bullet-list" id="switch-signals"></ul>
            </section>
            <section class="panel">
              <div class="eyebrow">Ejecucion y due diligence</div>
              <h2 class="panel-title">Plan recomendado</h2>
              <ul class="bullet-list" id="next-actions"></ul>
              <h2 class="panel-title" style="margin-top:20px;">Preguntas antes de ejecutar</h2>
              <ul class="bullet-list" id="due-diligence"></ul>
            </section>
          </div>
        </section>
      </main>
    </section>

    <footer class="site-footer">
      <div class="footer-glow" aria-hidden="true"></div>
      <div class="footer-mark" aria-hidden="true"></div>
      <div class="footer-meta" id="footer-meta"></div>
    </footer>
  </div>

  <script>
    const PAYLOAD = __PAYLOAD__;
    const AUDIENCE_META = {
      ceo: 'Prioriza asignacion de capital, payback y claridad de decision ejecutiva.',
      growth: 'Prioriza velocidad de aprendizaje, iteracion y escalado de palancas.',
      riesgo: 'Prioriza control del downside, robustez del suelo y criterios de contencion.',
    };
    const API_BASE = window.location.protocol.startsWith('http') ? window.location.origin : '';
    const BACKEND_ENABLED = Boolean(API_BASE);
    const PRECOMPUTED_STAGE_KEYS = new Set(['briefing', 'ingesta', 'uplift']);
    // briefing/ingesta/uplift no dependen de ejecución real (son datos ya
    // calculados), se marcan "done" desde el arranque para que la fase 4
    // (montecarlo) nunca aparezca bloqueada por una carrera con hydratePayload.
    const stageStatusInicial = {};
    PRECOMPUTED_STAGE_KEYS.forEach((key) => {
      stageStatusInicial[key] = { running: false, done: true };
    });
    const state = {
      activeStage: 'briefing',
      audience: 'ceo',
      autoTimer: null,
      progressTimer: null,
      autoplay: false,
      montecarloPollHandle: null,
      stageStatus: stageStatusInicial,
      backendReady: false,
    };

    function replacePayload(nextPayload) {
      Object.keys(PAYLOAD).forEach((key) => delete PAYLOAD[key]);
      Object.assign(PAYLOAD, nextPayload);
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    }

    function setConsoleBadges(runtimeText, runtimeMode, liveText, liveMode) {
      const runtime = document.getElementById('console-runtime-badge');
      const live = document.getElementById('console-live-badge');
      runtime.className = `status-chip ${runtimeMode || ''}`.trim();
      runtime.textContent = runtimeText;
      live.className = `status-chip ${liveMode || ''}`.trim();
      live.textContent = liveText;
      const hudRuntime = document.getElementById('hud-runtime');
      const hudLive = document.getElementById('hud-live');
      if (hudRuntime) hudRuntime.textContent = runtimeText;
      if (hudLive) hudLive.textContent = liveText;
    }

    function setConsoleOutput(stage, lines) {
      if (!stage) return;
      document.getElementById('console-stage-label').textContent = `${stage.eyebrow} · ${stage.title}`;
      document.getElementById('console-command').textContent = stage.command;
      document.getElementById('console-log').innerHTML = lines.map((line) => `<div>${line}</div>`).join('');
      const hudStage = document.getElementById('hud-active-stage');
      const hudTitle = document.getElementById('hud-active-title');
      const hudCopy = document.getElementById('hud-active-copy');
      if (hudStage) hudStage.textContent = stage.eyebrow;
      if (hudTitle) hudTitle.textContent = stage.title;
      if (hudCopy) hudCopy.textContent = stage.tagline;

      // la barra sticky superior refleja la fase activa y hereda su acento
      const topbarMsg = document.getElementById('topbar-msg');
      const topbarRight = document.getElementById('topbar-right');
      if (topbarMsg) topbarMsg.textContent = stage.tagline;
      if (topbarRight) topbarRight.textContent = `${stage.eyebrow} · ${stage.title}`;
      document.body.dataset.phaseAccent = stage.key;
    }

    function isStageLocked(stageKey) {
      const stages = asArray(PAYLOAD.stages);
      const index = stages.findIndex((s) => s.key === stageKey);
      if (index <= 0) return false;
      const previousKey = stages[index - 1].key;
      return !Boolean((state.stageStatus[previousKey] || {}).done);
    }

    function updateStageDecorators() {
      document.querySelectorAll('.stage-button').forEach((button) => {
        const stageKey = button.dataset.stage;
        const status = state.stageStatus[stageKey] || {};
        button.classList.toggle('running', Boolean(status.running));
        button.classList.toggle('done', Boolean(status.done));
        button.classList.toggle('active', stageKey === state.activeStage);
        // no se deshabilita el boton (el click debe seguir funcionando para
        // poder mostrar el modal de espera), solo se atenua visualmente.
        button.classList.toggle('locked', isStageLocked(stageKey) && stageKey !== state.activeStage);
      });
    }

    function fmtCurrency(value) {
      return Number(value || 0).toLocaleString('es-ES', { maximumFractionDigits: 0 }) + ' USD';
    }

    function fmtPct(value) {
      return (Number(value || 0) * 100).toFixed(1) + '%';
    }

    function fmtPctNumber(value) {
      return Number(value || 0).toFixed(1) + '%';
    }

    function asArray(value) {
      return Array.isArray(value) ? value : [];
    }

    function asObject(value) {
      return value && typeof value === 'object' ? value : {};
    }

    function createMetric(label, value, sub) {
      return `<article class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="stage-copy">${sub}</div></article>`;
    }

    // iconos de linea propios (sin libreria externa), circulo de color por fase
    const PHASE_ICONS = {
      briefing:  '<path d="M4 5h16M4 12h10M4 19h7"/>',
      ingesta:   '<path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"/><path d="M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
      uplift:    '<path d="M3 17l5-5 4 3 6-7"/><path d="M14 8h5v5"/>',
      montecarlo:'<circle cx="12" cy="12" r="8"/><path d="M12 4v8l5 3"/>',
      reporte:   '<path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4"/><path d="M9 12h7M9 16h5"/>',
    };
    const PHASE_COLORS = {
      briefing: 'var(--accent)', ingesta: 'var(--blue)', uplift: 'var(--pink)',
      montecarlo: 'var(--accent2)', reporte: 'var(--accent)',
    };
    const phaseIcon = (key) => `<span class="phase-icon" style="--icon-bg:${PHASE_COLORS[key] || 'var(--accent)'}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${PHASE_ICONS[key] || ''}</svg></span>`;

    const HERO_ROTATION = [
      { word: 'Carga y valida.', rest: '20,000 oportunidades comerciales historicas, listas para modelizar.', phase: 'ingesta' },
      { word: 'Modela el uplift.', rest: 'Regresion logistica + HistGradientBoosting por palanca.', phase: 'uplift' },
      { word: 'Simula 10,000 futuros.', rest: 'Montecarlo con incertidumbre real, no un escenario unico.', phase: 'montecarlo' },
      { word: 'Decide con datos.', rest: 'Recomendacion ejecutiva desde 3 roles de negocio.', phase: 'reporte' },
    ];

    function startHeroRotator() {
      const wordEl = document.getElementById('hero-rotator-word');
      const restEl = document.getElementById('hero-rotator-rest');
      const hero = document.querySelector('.hero');
      if (!wordEl || !restEl || !hero) return;

      let i = 0;
      const paint = () => {
        const state = HERO_ROTATION[i];
        wordEl.textContent = state.word;
        restEl.textContent = state.rest;
        hero.dataset.phaseAccent = state.phase;
        i = (i + 1) % HERO_ROTATION.length;
      };
      paint();

      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      setInterval(paint, 3000);
    }

    function renderHero() {
      const rawTitle = String(PAYLOAD.title || '');
      const cut = rawTitle.indexOf(' ', Math.floor(rawTitle.length / 2));
      const head = cut > 0 ? rawTitle.slice(0, cut) : rawTitle;
      const tail = cut > 0 ? rawTitle.slice(cut) : '';
      document.getElementById('hero-title').innerHTML =
        `${head}<span class="ghost-line">${tail}</span>`;
      document.getElementById('hero-subtitle').textContent = PAYLOAD.subtitle;
      const ds = asObject(asObject(PAYLOAD.dataset).summary);
      const simulation = asObject(PAYLOAD.simulation);
      const totalSimulations = Number(simulation.total_simulations || 0);
      const metrics = [
        createMetric('Oportunidades analizadas', ds.rows.toLocaleString('es-ES'), `${ds.period_start} -> ${ds.period_end}`),
        createMetric('Futuros a evaluar', totalSimulations.toLocaleString('es-ES'), 'Escenarios preparados para visualizar la toma de decision'),
        createMetric('Variables disponibles', ds.variable_count.toLocaleString('es-ES'), `${ds.segment_count} segmentos · ${ds.geography_count} geografias`),
        createMetric('Meses de historico', ds.time_windows.toLocaleString('es-ES'), 'Meses historicos disponibles para la decision'),
      ];
      document.getElementById('hero-kpis').innerHTML = metrics.join('');
      // coordenadas decorativas reales: periodo real del dataset, no lat/long inventado
      const coordLeft = document.getElementById('hero-coord-left');
      const coordRight = document.getElementById('hero-coord-right');
      if (coordLeft) coordLeft.textContent = ds.period_start || '';
      if (coordRight) coordRight.textContent = ds.period_end || '';

      renderTicker(ds, totalSimulations);

      const footerMeta = document.getElementById('footer-meta');
      if (footerMeta) {
        footerMeta.textContent = `${PAYLOAD.title} · ${ds.period_start} - ${ds.period_end}`;
      }
    }

    function renderTicker(ds, totalSimulations) {
      const track = document.getElementById('ticker-track');
      if (!track) return;
      const items = [
        `<strong>${ds.rows.toLocaleString('es-ES')}</strong> oportunidades históricas`,
        `<strong>${fmtPct(ds.conversion_rate)}</strong> conversión promedio`,
        `<strong>${fmtCurrency(ds.avg_ticket_usd)}</strong> ticket medio`,
        `<strong>${totalSimulations.toLocaleString('es-ES')}</strong> futuros simulados`,
        `<strong>${ds.variable_count}</strong> variables por oportunidad`,
        `<strong>${ds.geography_count}</strong> geografías cubiertas`,
      ];
      const html = items.map((item) => `<span class="ticker-item">${item}</span>`).join('');
      track.innerHTML = html + html; // duplicado para el loop continuo
    }

    function renderBriefing() {
      document.getElementById('briefing-tags').innerHTML = asArray(PAYLOAD.stages).map((stage) => `<span class="tag">${stage.eyebrow} · ${stage.title}</span>`).join('');
    }

    function renderStageButtons() {
      const root = document.getElementById('stage-buttons');
      root.innerHTML = asArray(PAYLOAD.stages).map((stage, idx) => `
        <button class="stage-button" data-stage="${stage.key}">
          <span class="stage-index">${String(idx + 1).padStart(2, '0')}</span>
          <span class="stage-body">
            ${phaseIcon(stage.key)}
            <span class="stage-title">${stage.title}</span>
            <span class="stage-copy">${stage.tagline}</span>
          </span>
        </button>
      `).join('');
      root.querySelectorAll('.stage-button').forEach((button) => {
        button.addEventListener('click', () => runStage(button.dataset.stage));
      });
      updateStageDecorators();
    }

    function renderDataset() {
      const dataset = asObject(PAYLOAD.dataset);
      const ds = asObject(dataset.summary);
      document.getElementById('dataset-kpis').innerHTML = [
        createMetric('Periodo cubierto', `${ds.period_start} -> ${ds.period_end}`, 'Ventana historica utilizada en el analisis'),
        createMetric('Conversion observada', fmtPct(ds.conversion_rate), 'Tasa media de exito del historico'),
        createMetric('Ticket medio', fmtCurrency(ds.avg_ticket_usd), 'Valor medio de las operaciones convertidas'),
        createMetric('Beneficio acumulado', fmtCurrency(ds.margen_neto_usd), 'Beneficio de contribucion total del historico'),
      ].join('');

      document.getElementById('dataset-structure-cards').innerHTML = [
        createMetric('Campañas', ds.campaign_count.toLocaleString('es-ES'), 'Campañas distintas ejecutadas en el periodo'),
        createMetric('Variables', ds.variable_count.toLocaleString('es-ES'), 'Campos disponibles para explicar comportamiento y resultado'),
        createMetric('Segmentos', ds.segment_count.toLocaleString('es-ES'), 'Segmentos de cliente cubiertos por el historico'),
        createMetric('Geografias', ds.geography_count.toLocaleString('es-ES'), 'Mercados donde opera la unidad'),
      ].join('');

      document.getElementById('sample-table').innerHTML = asArray(dataset.sample).map((row) => `
        <tr>
          <td>${row.date}</td>
          <td>${row.channel}</td>
          <td>${row.customer_segment}</td>
          <td>${row.ad_budget_level}</td>
          <td>${row.lead_score}</td>
          <td>${row.converted_to_sale ? 'Si' : 'No'}</td>
          <td>${fmtCurrency(row.revenue_usd)}</td>
          <td>${fmtCurrency(row.contribution_profit_usd)}</td>
        </tr>
      `).join('');

      renderMonthlyChart();
    }

    function renderMonthlyChart() {
      const svg = document.getElementById('monthly-chart');
      const data = asArray(asObject(PAYLOAD.dataset).monthly);
      if (!data.length) {
        svg.innerHTML = '';
        return;
      }
      const width = 680;
      const height = 280;
      const left = 42;
      const right = 22;
      const top = 24;
      const bottom = 28;
      const revenueValues = data.map((row) => Number(row.ingreso_usd));
      const profitValues = data.map((row) => Number(row.margen_neto_usd));
      const maxValue = Math.max(...revenueValues, ...profitValues, 1);
      const x = (index) => left + (index / Math.max(1, data.length - 1)) * (width - left - right);
      const y = (value) => height - bottom - (value / maxValue) * (height - top - bottom);
      const revenuePath = data.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(Number(row.ingreso_usd))}`).join(' ');
      const profitPath = data.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(Number(row.margen_neto_usd))}`).join(' ');
      const ticks = [0, 0.33, 0.66, 1].map((ratio) => {
        const tickY = y(maxValue * ratio);
        return `<line x1="${left}" y1="${tickY}" x2="${width - right}" y2="${tickY}" stroke="rgba(196, 188, 172, 0.10)" />`;
      }).join('');
      const labels = [data[0], data[Math.floor(data.length / 2)], data[data.length - 1]].map((row, idx) => {
        const positions = [left, width / 2, width - right];
        return `<text x="${positions[idx]}" y="${height - 8}" fill="#9c968c" font-size="11" text-anchor="middle">${row.month}</text>`;
      }).join('');
      svg.innerHTML = `
        <defs>
          <linearGradient id="rev-gradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stop-color="#d98e4a"></stop>
            <stop offset="100%" stop-color="#58a6ff"></stop>
          </linearGradient>
          <linearGradient id="profit-gradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stop-color="#27f5c6"></stop>
            <stop offset="100%" stop-color="#ffd166"></stop>
          </linearGradient>
        </defs>
        ${ticks}
        <path d="${revenuePath}" fill="none" stroke="url(#rev-gradient)" stroke-width="4" stroke-linecap="round"></path>
        <path d="${profitPath}" fill="none" stroke="url(#profit-gradient)" stroke-width="4" stroke-linecap="round" stroke-dasharray="8 8"></path>
        ${labels}
      `;
    }

    function renderUplift() {
      const models = asObject(PAYLOAD.models);
      const classification = asObject(models.classification);
      const regression = asObject(models.regression);
      const gainChart = asArray(classification.gain_chart);
      const residualBands = asArray(regression.residual_bands);
      const uplift = asObject(PAYLOAD.uplift);
      const mainUplift = asArray(uplift.main);
      const adsUplift = asArray(uplift.ads);
      document.getElementById('classification-kpis').innerHTML = [
        createMetric('AUC', Number(classification.auc).toFixed(3), 'Capacidad de separar oportunidades con mayor y menor probabilidad de exito'),
        createMetric('Base de conversion', fmtPct(classification.positive_rate), 'Frecuencia observada de cierres en el conjunto de validacion'),
        createMetric('Probabilidad media', fmtPct(classification.avg_predicted_prob), 'Propension media estimada por el modelo'),
        createMetric('Top decil', fmtPct(gainChart[0] ? gainChart[0].conversion_rate : 0), 'Tasa de conversion del 10% de casos con mayor puntuacion'),
      ].join('');

      document.getElementById('regression-kpis').innerHTML = [
        createMetric('MAE', fmtCurrency(regression.mae_usd), 'Error absoluto medio sobre el valor estimado'),
        createMetric('R²', Number(regression.r2).toFixed(3), 'Capacidad del modelo para explicar variacion del ticket'),
        createMetric('Sesgo medio', fmtCurrency(regression.mean_residual_usd), 'Diferencia media entre valor real y valor estimado'),
        createMetric('P90 error', fmtCurrency(regression.p90_abs_error_usd), 'Error absoluto en el percentil 90'),
      ].join('');

      renderGainChart();
      const maxResidualCount = Math.max(...residualBands.map((row) => Number(row.count)), 1);
      document.getElementById('residual-bars').innerHTML = residualBands.map((row) => `
        <div class="bar-row">
          <div>
            <div class="stage-title" style="font-size:15px">${row.label}</div>
            <div class="stage-copy">Numero de observaciones dentro de esta banda de error</div>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.max(8, Number(row.count) / maxResidualCount * 100)}%"></div></div>
          <div style="text-align:right">${Number(row.count).toLocaleString('es-ES')}</div>
        </div>
      `).join('');

      const upliftRoot = document.getElementById('uplift-cards');
      upliftRoot.innerHTML = mainUplift.map((row) => `
        <article class="tool-card flash">
          <div class="eyebrow">${row.label}</div>
          <div class="tool-name">${fmtPct(row.baseline_cobertura)} → ${fmtPct(row.scenario_conversion)} de conversion esperada</div>
          <div class="tool-purpose">${row.description} Uplift estimado: ${fmtPctNumber(Number(row.conversion_lift_pct) * 100)} · Impacto incremental por oportunidad: ${fmtCurrency(row.profit_lift_per_window_usd)}</div>
        </article>
      `).join('');

    }

    function renderGainChart() {
      const svg = document.getElementById('gain-chart');
      const data = asArray(asObject(asObject(PAYLOAD.models).classification).gain_chart);
      if (!data.length) {
        svg.innerHTML = '';
        return;
      }
      const width = 680;
      const height = 240;
      const left = 42;
      const right = 18;
      const top = 20;
      const bottom = 28;
      const x = (index) => left + (index / Math.max(1, data.length - 1)) * (width - left - right);
      const y = (value) => height - bottom - value * (height - top - bottom);
      const gainPath = data.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index)} ${y(Number(row.capture_pct))}`).join(' ');
      const basePath = `M ${left} ${y(0.1)} ${data.map((row, index) => `L ${x(index)} ${y((index + 1) / 10)}`).join(' ')}`;
      const points = data.map((row, index) => `<circle cx="${x(index)}" cy="${y(Number(row.capture_pct))}" r="4" fill="#d98e4a"></circle>`).join('');
      svg.innerHTML = `
        <line x1="${left}" y1="${y(0)}" x2="${width - right}" y2="${y(0)}" stroke="rgba(196, 188, 172, 0.12)" />
        <line x1="${left}" y1="${y(0.5)}" x2="${width - right}" y2="${y(0.5)}" stroke="rgba(196, 188, 172, 0.12)" />
        <line x1="${left}" y1="${y(1)}" x2="${width - right}" y2="${y(1)}" stroke="rgba(196, 188, 172, 0.12)" />
        <path d="${basePath}" fill="none" stroke="#ffd166" stroke-width="2" stroke-dasharray="8 8"></path>
        <path d="${gainPath}" fill="none" stroke="#d98e4a" stroke-width="4" stroke-linecap="round"></path>
        ${points}
        <text x="${left}" y="18" fill="#9c968c" font-size="11">Captura acumulada de conversiones</text>
        <text x="${width - right}" y="18" text-anchor="end" fill="#9c968c" font-size="11">Gain chart</text>
      `;
    }

    function renderSimulation() {
      const simulation = asObject(PAYLOAD.simulation);
      const summary = asArray(simulation.summary);
      document.getElementById('summary-cards').innerHTML = summary.map((row) => `
        <article class="tool-card">
          <div class="eyebrow">Ranking ${row.ranking}</div>
          <div class="tool-name">${row.decision}</div>
          <div class="tool-purpose">Beneficio esperado: ${fmtCurrency(row.expected_profit_usd)} · P10: ${fmtCurrency(row.p10_usd)} · P90: ${fmtCurrency(row.p90_usd)} · ROI: ${Number(row.expected_roi).toFixed(1)}x</div>
        </article>
      `).join('');
      refreshLiveFrame(false);
    }

    function renderReport() {
      const recommendation = asObject(PAYLOAD.recommendation);
      const report = asObject(PAYLOAD.report);
      const audienceViews = asObject(recommendation.audience_views);
      const selectedView = asObject(audienceViews[state.audience]);
      const activeView = Object.keys(selectedView).length ? selectedView : recommendation;
      document.getElementById('audience-summary').textContent = AUDIENCE_META[state.audience] || '';
      document.getElementById('verdict-headline').textContent = activeView.headline || recommendation.headline;
      document.getElementById('verdict-copy').textContent = activeView.summary || recommendation.agent_summary || `${recommendation.decision} lidera la simulacion con ${fmtCurrency(recommendation.expected_profit_usd)}, ROI esperado de ${Number(recommendation.expected_roi).toFixed(1)}x y probabilidad de perdida de ${fmtPct(recommendation.probability_loss)}.`;
      document.getElementById('reason-list').innerHTML = asArray(activeView.reasons || recommendation.reasons).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('watchouts-list').innerHTML = asArray(activeView.watchouts || recommendation.watchouts).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('next-actions').innerHTML = asArray(activeView.next_actions || recommendation.next_actions).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('switch-signals').innerHTML = asArray(activeView.switch_signals || recommendation.switch_signals).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('due-diligence').innerHTML = asArray(activeView.due_diligence || recommendation.due_diligence).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('agent-findings').innerHTML = asArray(recommendation.findings).map((item) => `<li>${item}</li>`).join('');
      document.getElementById('tool-trace').innerHTML = asArray(recommendation.tool_trace).map((item) => `
        <article class="trace-item">
          <div class="trace-top">
            <div class="trace-name">${item.name}</div>
            <div class="trace-args">${item.args}</div>
          </div>
          <div class="trace-purpose">${item.purpose}</div>
          <div class="trace-outcome">${item.outcome}</div>
        </article>
      `).join('');
      document.querySelectorAll('[data-audience]').forEach((button) => {
        button.classList.toggle('active', button.dataset.audience === state.audience);
      });
      document.getElementById('report-checks').innerHTML = asArray(report.checks).map((item) => `<span class="tag">${item}</span>`).join('');
    }

    function consoleLines(stage) {
      const base = [
        `> ${stage.command}`,
        '> preparando la vista ejecutiva',
        '> actualizando la consola con informacion del caso',
      ];
      if (stage.key === 'ingesta') return base.concat(['> cargando base historica', '> validando cobertura y estructura de variables']);
      if (stage.key === 'uplift') return base.concat(['> calculando metricas tecnicas de los modelos', '> traduciendo resultados a escenarios de negocio']);
      if (stage.key === 'montecarlo') return base.concat(['> iniciando simulacion de escenarios', '> sincronizando radar y telemetria en directo']);
      if (stage.key === 'reporte') return base.concat(['> consolidando conclusiones', '> preparando recomendacion ejecutiva']);
      return base.concat(['> consola lista para iniciar la presentacion']);
    }

    function showPane(stageKey) {
      document.querySelectorAll('.stage-pane').forEach((pane) => pane.classList.remove('active'));
      document.getElementById(`pane-${stageKey}`).classList.add('active');
      state.activeStage = stageKey;
      updateStageDecorators();
    }

    function runProgress(stage, durationMs, onDone) {
      clearInterval(state.progressTimer);
      const fill = document.getElementById('progress-fill');
      const start = performance.now();
      fill.style.width = '0%';
      state.progressTimer = setInterval(() => {
        const elapsed = performance.now() - start;
        const pct = Math.min(100, elapsed / Math.max(1, durationMs) * 100);
        fill.style.width = pct + '%';
        if (pct >= 100) {
          clearInterval(state.progressTimer);
          showPane(stage.key);
          if (onDone) onDone();
        }
      }, 32);
    }

    function refreshLiveFrame(withTimestamp = true) {
      const frame = document.getElementById('live-frame');
      const base = asObject(PAYLOAD.simulation).live_dashboard || 'dashboards/dashboard_live_montecarlo.html';
      frame.src = withTimestamp ? `${base}?ts=${Date.now()}` : base;
    }

    function setMontecarloPlaceholder(visible, title = '', copy = '') {
      const root = document.getElementById('montecarlo-placeholder');
      if (!root) return;
      root.classList.toggle('is-visible', Boolean(visible));
      if (title) document.getElementById('montecarlo-placeholder-title').textContent = title;
      if (copy) document.getElementById('montecarlo-placeholder-copy').textContent = copy;
    }

    function syncLiveFrameHeight() {
      const frame = document.getElementById('live-frame');
      if (!frame) return;
      try {
        const doc = frame.contentDocument || frame.contentWindow?.document;
        if (!doc) return;
        const shell = doc.querySelector('.shell');
        const measuredHeight = shell
          ? shell.scrollHeight + 32
          : Math.max(doc.documentElement.scrollHeight || 0, doc.body ? doc.body.scrollHeight : 0);
        const nextHeight = Math.min(1800, Math.max(1040, measuredHeight));
        frame.style.height = `${nextHeight}px`;
      } catch (error) {
        // same-origin in local mode, but keep this resilient if the source changes.
      }
    }

    function renderAll() {
      renderHero();
      renderBriefing();
      renderDataset();
      renderUplift();
      renderSimulation();
      renderReport();
      updateStageDecorators();
    }

    function activateStage(stageKey, instant = false) {
      const stage = asArray(PAYLOAD.stages).find((item) => item.key === stageKey);
      if (!stage) return;
      setConsoleOutput(stage, consoleLines(stage));
      if (instant) {
        document.getElementById('progress-fill').style.width = '100%';
        showPane(stage.key);
        return;
      }
      runProgress(stage, stage.duration_ms);
    }

    async function hydratePayload() {
      if (!BACKEND_ENABLED) {
        setConsoleBadges('Modo local', 'ready', 'Sin backend', '');
        return;
      }
      try {
        const response = await fetchJson(`${API_BASE}/api/payload`);
        replacePayload(response.payload);
        state.backendReady = true;

        // las 3 primeras fases ya vienen precalculadas del backend: al
        // recargar la pagina no hace falta re-clickearlas para desbloquear
        // el resto de la secuencia.
        PRECOMPUTED_STAGE_KEYS.forEach((key) => {
          state.stageStatus[key] = { running: false, done: true };
        });

        renderAll();
        setConsoleBadges('Backend online', 'ready', 'Aplicacion sincronizada', 'ready');
        const live = await fetchJson(`${API_BASE}/api/montecarlo-status`);
        if (live.preparing) {
          setMontecarloPlaceholder(true, 'Precalculando simulacion', live.status_message || 'Preparando dataset y modelos antes de arrancar la simulacion real.');
          beginMontecarloPolling();
        } else if (live.running || live.is_running) {
          setMontecarloPlaceholder(false);
          state.stageStatus.montecarlo = { running: true, done: false };
          beginMontecarloPolling();
        } else if (live.completed) {
          // la simulación ya termino en una sesión anterior del servidor:
          // se recupera el estado "done" en vez de dejar la fase bloqueada.
          setMontecarloPlaceholder(false);
          state.stageStatus.montecarlo = { running: false, done: true };
        }
        updateStageDecorators();
      } catch (error) {
        setConsoleBadges('Modo local', 'alert', 'Backend no accesible', 'alert');
      }
    }

    async function runStage(stageKey, options = {}) {
      const stage = asArray(PAYLOAD.stages).find((item) => item.key === stageKey);
      if (!stage) return;

      // fase todavía no alcanzable (la anterior no ha terminado): en vez de
      // no hacer nada, se explica por que con un modal.
      if (!options.fromWaitModal && isStageLocked(stageKey)) {
        showWaitModal(stageKey);
        return;
      }

      // montecarlo ya corriendo o ya terminado: solo muestra el panel, nunca
      // relanza la simulación desde 0% por un click repetido.
      if (stageKey === 'montecarlo') {
        const mcStatus = state.stageStatus.montecarlo || {};
        if (mcStatus.running || mcStatus.done) {
          state.activeStage = stageKey;
          updateStageDecorators();
          showPane(stageKey);
          return;
        }
      }

      if (!options.keepAutoplay) {
        state.autoplay = false;
        clearTimeout(state.autoTimer);
      }

      if (!BACKEND_ENABLED) {
        activateStage(stageKey, options.instant === true);
        return;
      }

      if (state.backendReady && PRECOMPUTED_STAGE_KEYS.has(stageKey)) {
        state.stageStatus[stageKey] = { running: false, done: true };
        updateStageDecorators();
        showPane(stage.key);
        setConsoleBadges('Backend online', 'ready', `${stage.title} preparada`, 'ready');
        setConsoleOutput(stage, consoleLines(stage));
        document.getElementById('progress-fill').style.width = '100%';
        return;
      }

      const autoplayButton = document.getElementById('autoplay-btn');
      autoplayButton.disabled = true;
      state.stageStatus[stageKey] = { running: true, done: false };
      updateStageDecorators();
      setConsoleOutput(stage, ['> contactando backend local', '> preparando ejecucion real de la etapa']);
      if (stageKey === 'montecarlo') {
        showPane(stage.key);
        document.getElementById('progress-fill').style.width = '0%';
      }

      try {
        const response = await fetchJson(`${API_BASE}/api/stage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stage: stageKey }),
        });
        if (response.payload) {
          replacePayload(response.payload);
          renderAll();
        }
        setConsoleOutput(stage, response.logs || consoleLines(stage));
        const liveLabel = stageKey === 'montecarlo'
          ? 'Simulacion en directo'
          : `${stage.title} completada`;
        if (stageKey === 'montecarlo' && response.status === 'preparing') {
          setConsoleBadges('Backend online', 'ready', 'Precalculando simulacion', 'running');
          setMontecarloPlaceholder(true, 'Precalculando simulacion', 'El backend está preparando dataset y modelos. El dashboard live aparecerá cuando arranque la simulación real.');
          beginMontecarloPolling();
          return;
        }
        setConsoleBadges('Backend online', 'ready', liveLabel, stageKey === 'montecarlo' ? 'running' : 'ready');
        if (stageKey === 'montecarlo') {
          state.stageStatus[stageKey] = {
            running: Boolean(response.montecarlo && response.montecarlo.running),
            done: false,
          };
          updateStageDecorators();
          setMontecarloPlaceholder(false);
          refreshLiveFrame(true);
          beginMontecarloPolling();
          return;
        }
        const delayMs = options.instant ? 1 : Number(response.delay_ms || stage.duration_ms || 900);
        runProgress(stage, delayMs, () => {
          state.stageStatus[stageKey] = {
            running: stageKey === 'montecarlo' && response.montecarlo && response.montecarlo.running,
            done: stageKey !== 'montecarlo',
          };
          updateStageDecorators();
          if (stageKey === 'montecarlo') {
            refreshLiveFrame(true);
            beginMontecarloPolling();
          }
        });
      } catch (error) {
        state.stageStatus[stageKey] = { running: false, done: false };
        updateStageDecorators();
        setConsoleBadges('Backend error', 'alert', 'Etapa no ejecutada', 'alert');
        setConsoleOutput(stage, [`> error al ejecutar la etapa`, `> ${error.message}`]);
      } finally {
        autoplayButton.disabled = false;
      }
    }

    function typewriteText(el, text) {
      // efecto maquina de escribir, como el modal "a note from us" de
      // legend.xyz. se salta la animación si el usuario pide menos movimiento.
      if (el._typewriteTimer) clearInterval(el._typewriteTimer);
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduce) {
        el.textContent = text;
        return;
      }
      el.textContent = '';
      let i = 0;
      el._typewriteTimer = setInterval(() => {
        i += 1;
        el.textContent = text.slice(0, i);
        if (i >= text.length) clearInterval(el._typewriteTimer);
      }, 14);
    }

    function showWaitModal(stageKey) {
      const stages = asArray(PAYLOAD.stages);
      const stage = stages.find((s) => s.key === stageKey);
      const index = stages.findIndex((s) => s.key === stageKey);
      const blocking = index > 0 ? stages[index - 1] : null;
      const overlay = document.getElementById('wait-modal-overlay');
      const title = document.getElementById('wait-modal-title');
      const copy = document.getElementById('wait-modal-copy');
      const progressBlock = document.querySelector('.wait-modal-progress');
      const gotoBtn = document.getElementById('wait-modal-goto');

      const waitingOnMontecarlo = blocking && blocking.key === 'montecarlo';
      if (waitingOnMontecarlo) {
        title.textContent = 'Simulacion en curso';
        typewriteText(copy, `${stage ? stage.title : 'Esta fase'} se arma con los resultados de la simulacion Monte Carlo. Espera a que termine para poder verla.`);
        progressBlock.style.display = '';
        gotoBtn.style.display = '';
      } else {
        title.textContent = 'Fase anterior pendiente';
        typewriteText(copy, `Antes de "${stage ? stage.title : 'esta fase'}" hace falta completar "${blocking ? blocking.title : 'la fase anterior'}".`);
        progressBlock.style.display = 'none';
        gotoBtn.style.display = 'none';
      }

      overlay.dataset.pendingStage = stageKey;
      overlay.classList.add('is-visible');
      const mcStatus = state.stageStatus.montecarlo || {};
      updateWaitModalProgress(0, Boolean(mcStatus.running));
      if (waitingOnMontecarlo && !mcStatus.running && !mcStatus.done) {
        // la simulación ni siquiera se ha lanzado todavía: lanzarla ahora
        // para que el usuario no tenga que cerrar el modal y hacerlo aparte.
        runStage('montecarlo');
      }
    }

    function hideWaitModal() {
      document.getElementById('wait-modal-overlay').classList.remove('is-visible');
    }

    function updateWaitModalProgress(pct, isRunning) {
      const overlay = document.getElementById('wait-modal-overlay');
      if (!overlay.classList.contains('is-visible')) return;
      document.getElementById('wait-modal-pct').textContent = `${pct.toFixed(0)}%`;
      document.getElementById('wait-modal-bar').style.width = `${pct}%`;
      if (!isRunning && pct >= 100) {
        const pending = overlay.dataset.pendingStage;
        hideWaitModal();
        if (pending) runStage(pending, { fromWaitModal: true });
      }
    }

    async function pollMontecarloStatus() {
      try {
        const status = await fetchJson(`${API_BASE}/api/montecarlo-status`);
        const pct = Number(status.progress_pct || 0);
        document.getElementById('progress-fill').style.width = `${pct}%`;
        updateWaitModalProgress(pct, Boolean(status.running || status.is_running));
        if (status.preparing && !status.running && !status.is_running) {
          const montecarloStage = asArray(PAYLOAD.stages).find((item) => item.key === 'montecarlo');
          setConsoleBadges('Backend online', 'ready', 'Precalculando simulacion', 'running');
          setConsoleOutput(
            montecarloStage,
            [
              '> precalculando dataset y modelos',
              '> preparando el punto de partida de la simulacion real',
              `> estado: ${status.status_message || 'esperando activos de simulacion'}`,
            ],
          );
          setMontecarloPlaceholder(true, 'Precalculando simulacion', status.status_message || 'Preparando dataset y modelos antes de arrancar la simulación real.');
          return;
        }
        if (status.running || status.is_running) {
          const leaderText = status.leader ? status.leader.decision : 'calculando ranking';
          const montecarloStage = asArray(PAYLOAD.stages).find((item) => item.key === 'montecarlo');
          setConsoleBadges('Backend online', 'ready', `Monte Carlo ${pct.toFixed(1)}%`, 'running');
          setMontecarloPlaceholder(false);
          setConsoleOutput(
            montecarloStage,
            [
              '> simulacion Monte Carlo en curso',
              `> iteracion ${Number(status.current_simulation || 0).toLocaleString('es-ES')} de ${Number(status.total_simulations || 0).toLocaleString('es-ES')}`,
              `> avance visible: ${pct.toFixed(1)}%`,
              `> mejor alternativa provisional: ${leaderText}`,
            ],
          );
          if (state.activeStage === 'montecarlo') {
            refreshLiveFrame(true);
            syncLiveFrameHeight();
          }
          return;
        }

        clearInterval(state.montecarloPollHandle);
        state.montecarloPollHandle = null;
        state.stageStatus.montecarlo = { running: false, done: true };
        if (status.payload) {
          replacePayload(status.payload);
          renderAll();
        }
        document.getElementById('progress-fill').style.width = '100%';
        const montecarloStage = asArray(PAYLOAD.stages).find((item) => item.key === 'montecarlo');
        setConsoleBadges('Backend online', 'ready', 'Monte Carlo completada', 'ready');
        setMontecarloPlaceholder(false);
        setConsoleOutput(
          montecarloStage,
          [
            '> simulacion finalizada',
            `> iteraciones finales: ${Number(status.total_simulations || 0).toLocaleString('es-ES')}`,
            `> mejor alternativa: ${status.leader ? status.leader.decision : 'sin ranking'}`,
            '> resultados consolidados listos para la recomendacion final',
          ],
        );
        updateStageDecorators();
        refreshLiveFrame(true);
        syncLiveFrameHeight();
      } catch (error) {
        clearInterval(state.montecarloPollHandle);
        state.montecarloPollHandle = null;
        setConsoleBadges('Backend online', 'ready', 'Error monitorizando live', 'alert');
      }
    }

    function beginMontecarloPolling() {
      clearInterval(state.montecarloPollHandle);
      state.montecarloPollHandle = setInterval(pollMontecarloStatus, 1200);
      pollMontecarloStatus();
    }

    function autoplaySequence() {
      clearTimeout(state.autoTimer);
      const order = asArray(PAYLOAD.stages).map((stage) => stage.key);
      let index = 0;
      state.autoplay = true;
      async function next() {
        await runStage(order[index], { keepAutoplay: true });
        index += 1;
        if (index < order.length && state.autoplay) {
          const previous = order[index - 1];
          const waitMs = previous === 'montecarlo' ? 42000 : 4800;
          state.autoTimer = setTimeout(next, waitMs);
        }
      }
      next();
    }

    async function relanzarMontecarlo() {
      const boton = document.getElementById('relanzar-montecarlo-btn');
      boton.disabled = true;
      try {
        await fetchJson(`${API_BASE}/api/montecarlo-reset`, { method: 'POST' });
      } catch (error) {
        setConsoleBadges('Backend error', 'alert', 'No se pudo relanzar', 'alert');
        boton.disabled = false;
        return;
      }
      // limpia el estado local de montecarlo y reporte (el informe depende
      // de la simulación anterior, ya no es valido) y relanza desde 0%.
      state.stageStatus.montecarlo = { running: false, done: false };
      state.stageStatus.reporte = { running: false, done: false };
      updateStageDecorators();
      boton.disabled = false;
      runStage('montecarlo');
    }

    function bindActions() {
      document.getElementById('autoplay-btn').addEventListener('click', autoplaySequence);
      const relanzarBtn = document.getElementById('relanzar-montecarlo-btn');
      if (relanzarBtn) relanzarBtn.addEventListener('click', relanzarMontecarlo);
      const waitOverlay = document.getElementById('wait-modal-overlay');
      document.getElementById('wait-modal-close').addEventListener('click', hideWaitModal);
      document.getElementById('wait-modal-goto').addEventListener('click', () => {
        hideWaitModal();
        runStage('montecarlo');
      });
      waitOverlay.addEventListener('click', (event) => {
        if (event.target === waitOverlay) hideWaitModal();
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') hideWaitModal();
      });
      document.querySelectorAll('[data-audience]').forEach((button) => {
        button.addEventListener('click', () => {
          state.audience = button.dataset.audience || 'ceo';
          renderReport();
        });
      });
      document.getElementById('reset-btn').addEventListener('click', () => {
        state.autoplay = false;
        state.audience = 'ceo';
        clearTimeout(state.autoTimer);
        clearInterval(state.montecarloPollHandle);
        state.montecarloPollHandle = null;
        activateStage('briefing', true);
        setConsoleBadges(BACKEND_ENABLED ? 'Backend online' : 'Modo local', 'ready', BACKEND_ENABLED ? 'Consola lista' : 'Sin backend', BACKEND_ENABLED ? 'ready' : '');
      });
      const liveFrame = document.getElementById('live-frame');
      if (liveFrame) {
        liveFrame.addEventListener('load', syncLiveFrameHeight);
      }
    }

    async function init() {
      renderAll();
      renderStageButtons();
      bindActions();
      startHeroRotator();
      activateStage('briefing', true);
      await hydratePayload();
    }

    init();
  </script>

  <div class="wait-modal-overlay" id="wait-modal-overlay">
    <div class="wait-modal" role="dialog" aria-modal="true" aria-labelledby="wait-modal-title">
      <div class="placeholder-ring"></div>
      <div class="wait-modal-title" id="wait-modal-title">Simulacion en curso</div>
      <p class="wait-modal-copy" id="wait-modal-copy">
        El informe final se arma con los resultados de la simulacion Monte Carlo. Espera a que
        termine para poder verlo.
      </p>
      <div class="wait-modal-progress">
        <div class="wait-modal-pct" id="wait-modal-pct">0%</div>
        <div class="bar-track"><div class="bar-fill" id="wait-modal-bar" style="width: 0%"></div></div>
      </div>
      <div class="wait-modal-actions">
        <button type="button" class="action action-primary" id="wait-modal-goto">Ver simulacion en vivo</button>
        <button type="button" class="action" id="wait-modal-close">Cerrar</button>
      </div>
    </div>
  </div>
</body>
</html>
"""


def generate_mission_dashboard(output_path: Path = MISSION_DASHBOARD_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    path = generate_mission_dashboard()
    print(path)


if __name__ == "__main__":
    main()