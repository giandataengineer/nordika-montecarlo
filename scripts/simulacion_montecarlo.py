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


CHANNELS = [
    "Facebook Ads",
    "Google Ads",
    "TikTok Ads",
    "SEO / Blog",
    "Email",
    "Afiliados",
    "Webinar",
]

SEGMENTS = ["Creator", "Ecommerce", "B2B Services", "SMB", "Enterprise"]
DEVICES = ["desktop", "mobile", "tablet"]
REGIONS = ["ES", "MX", "CO", "US Hispanic", "AR", "CL"]
OBJECTIVES = ["cold_acquisition", "retargeting", "nurture", "launch", "evergreen"]


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1 / (1 + np.exp(-x))


def choose(rng: np.random.Generator, values: list[str], probs: list[float]) -> str:
    return str(rng.choice(values, p=np.array(probs) / np.sum(probs)))


def ad_budget_level(date: pd.Timestamp, channel: str) -> str:
    if channel not in {"Facebook Ads", "Google Ads", "TikTok Ads"}:
        return "organic_or_owned"

    ym = date.year * 100 + date.month
    if ym <= 202404:
        return "low"
    if ym <= 202408:
        return "medium"
    if ym <= 202412:
        return "high"
    if ym <= 202503:
        return "medium"
    if ym <= 202506:
        return "saturated"
    if ym <= 202509:
        return "medium"
    if ym <= 202512:
        return "high"
    if ym <= 202602:
        return "saturated"
    return "medium"


def generate_dates(rng: np.random.Generator) -> pd.DatetimeIndex:
    dates = pd.date_range("2024-01-01", "2026-04-30", freq="D")
    t = np.arange(len(dates))
    trend = 1 + 0.0009 * t
    seasonality = 1 + 0.10 * np.sin(2 * np.pi * (dates.dayofyear.to_numpy() / 365.25))
    launch_bump = np.where((dates >= "2025-10-01") & (dates <= "2025-12-15"), 1.16, 1.0)
    weights = trend * seasonality * launch_bump
    weights = weights / weights.sum()
    return pd.DatetimeIndex(rng.choice(dates, size=N_ROWS, replace=True, p=weights)).sort_values()


def generate_dataset() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = generate_dates(rng)
    rows = []

    for idx, date in enumerate(dates, start=1):
        month_index = (date.year - 2024) * 12 + date.month - 1
        quarter = f"{date.year}Q{((date.month - 1) // 3) + 1}"

        if date < pd.Timestamp("2024-09-01"):
            channel_probs = [0.21, 0.15, 0.13, 0.17, 0.18, 0.10, 0.06]
        elif date < pd.Timestamp("2025-04-01"):
            channel_probs = [0.24, 0.16, 0.12, 0.15, 0.16, 0.09, 0.08]
        elif date < pd.Timestamp("2025-07-01"):
            channel_probs = [0.31, 0.19, 0.09, 0.12, 0.13, 0.08, 0.08]
        else:
            channel_probs = [0.23, 0.16, 0.12, 0.15, 0.17, 0.08, 0.09]
        channel = choose(rng, CHANNELS, channel_probs)

        segment = choose(rng, SEGMENTS, [0.20, 0.24, 0.24, 0.22, 0.10])
        device = choose(rng, DEVICES, [0.58, 0.35, 0.07])
        geo_region = choose(rng, REGIONS, [0.46, 0.18, 0.10, 0.08, 0.10, 0.08])
        lifecycle_stage = choose(rng, ["new_visitor", "known_lead", "returning_customer"], [0.54, 0.34, 0.12])

        if channel in {"Facebook Ads", "Google Ads"}:
            campaign_objective = choose(rng, OBJECTIVES, [0.48, 0.26, 0.08, 0.12, 0.06])
        elif channel in {"Email", "Webinar"}:
            campaign_objective = choose(rng, OBJECTIVES, [0.03, 0.18, 0.50, 0.12, 0.17])
        else:
            campaign_objective = choose(rng, OBJECTIVES, [0.22, 0.12, 0.18, 0.08, 0.40])

        budget_level = ad_budget_level(date, channel)
        budget_multiplier = {
            "organic_or_owned": 0,
            "low": 0.70,
            "medium": 1.00,
            "high": 1.65,
            "saturated": 2.55,
        }[budget_level]

        base_daily_spend = {"Facebook Ads": 420, "Google Ads": 310, "TikTok Ads": 265}.get(channel, 0)
        campaign_daily_spend = max(0, rng.normal(base_daily_spend * budget_multiplier, 35 + base_daily_spend * 0.08))

        base_cost = {
            "Facebook Ads": 12.5,
            "Google Ads": 10.5,
            "Afiliados": 7.0,
            "Webinar": 5.5,
            "SEO / Blog": 1.8,
            "TikTok Ads": 8.4,
            "Email": 0.7,
        }[channel]
        saturation_cost = {"low": 0.88, "medium": 1.00, "high": 1.28, "saturated": 1.82, "organic_or_owned": 1.0}[budget_level]
        cost_attributed = max(0.15, rng.lognormal(np.log(base_cost * saturation_cost), 0.22))

        if date < pd.Timestamp("2024-09-15"):
            landing_variant = "baseline"
        elif date < pd.Timestamp("2025-01-01"):
            landing_variant = choose(rng, ["baseline", "landing_v2"], [0.58, 0.42])
        else:
            landing_variant = choose(rng, ["baseline", "landing_v2"], [0.30, 0.70])

        if date < pd.Timestamp("2025-03-15"):
            cta_variant = "standard"
        elif date < pd.Timestamp("2025-07-01"):
            cta_variant = choose(rng, ["standard", "benefit_cta"], [0.52, 0.48])
        else:
            cta_variant = choose(rng, ["standard", "benefit_cta"], [0.28, 0.72])

        if date < pd.Timestamp("2025-03-15"):
            lead_magnet = 0
        elif date < pd.Timestamp("2025-07-01"):
            lead_magnet = int(rng.random() < 0.42)
        else:
            lead_magnet = int(rng.random() < 0.76)

        if date < pd.Timestamp("2025-08-01"):
            checkout_simplified = 0
        else:
            checkout_simplified = int(rng.random() < 0.64)

        warm_enough = lifecycle_stage != "new_visitor" or channel in {"Email", "Webinar", "SEO / Blog"}
        webinar_invited = int(date >= pd.Timestamp("2025-01-10") and warm_enough and rng.random() < 0.27)
        attendance_prob = 0.17
        attendance_prob += 0.14 if channel in {"Email", "Webinar"} else 0
        attendance_prob += 0.07 if lifecycle_stage == "returning_customer" else 0
        attendance_prob += 0.05 if segment in {"B2B Services", "Enterprise"} else 0
        webinar_attended = int(webinar_invited and rng.random() < min(attendance_prob, 0.55))

        eligible_new_product = segment in {"Enterprise", "B2B Services", "Ecommerce"}
        if date < pd.Timestamp("2025-10-01"):
            new_product_offer = 0
        elif date < pd.Timestamp("2026-01-15"):
            new_product_offer = int(eligible_new_product and rng.random() < 0.18)
        else:
            new_product_offer = int(eligible_new_product and rng.random() < 0.12)

        channel_quality = {
            "Email": 14,
            "Webinar": 12,
            "SEO / Blog": 8,
            "TikTok Ads": -3,
            "Google Ads": 1,
            "Afiliados": -1,
            "Facebook Ads": -4,
        }[channel]
        segment_quality = {"Enterprise": 8, "B2B Services": 6, "Ecommerce": 3, "Creator": 0, "SMB": -2}[segment]
        lifecycle_quality = {"new_visitor": -6, "known_lead": 5, "returning_customer": 12}[lifecycle_stage]
        saturation_quality = {"organic_or_owned": 0, "low": 3, "medium": 0, "high": -6, "saturated": -15}[budget_level]
        quality = 52 + channel_quality + segment_quality + lifecycle_quality + saturation_quality + rng.normal(0, 11)
        lead_score = int(np.clip(round(quality), 1, 99))

        logit = -3.15
        logit += (lead_score - 50) * 0.032
        logit += {
            "Email": 0.34,
            "Webinar": 0.46,
            "SEO / Blog": 0.16,
            "TikTok Ads": -0.10,
            "Google Ads": -0.03,
            "Afiliados": -0.08,
            "Facebook Ads": -0.16,
        }[channel]
        logit += {"Creator": -0.04, "Ecommerce": 0.08, "B2B Services": 0.12, "SMB": -0.10, "Enterprise": 0.04}[segment]
        logit += {"new_visitor": -0.16, "known_lead": 0.22, "returning_customer": 0.38}[lifecycle_stage]
        logit += {"cold_acquisition": -0.18, "retargeting": 0.16, "nurture": 0.22, "launch": -0.04, "evergreen": 0.03}[campaign_objective]
        logit += 0.19 if landing_variant == "landing_v2" else 0
        logit += 0.18 if cta_variant == "benefit_cta" else 0
        logit += 0.21 if lead_magnet else 0
        logit += 0.16 if checkout_simplified else 0
        logit += 0.48 if webinar_attended else (0.04 if webinar_invited else 0)
        logit += {"organic_or_owned": 0, "low": 0.06, "medium": 0, "high": -0.15, "saturated": -0.48}[budget_level]
        logit += -0.22 if new_product_offer else 0
        logit += 0.004 * month_index
        conversion_prob = float(np.clip(sigmoid(logit), 0.005, 0.58))
        converted = int(rng.random() < conversion_prob)

        base_aov = {"Creator": 760, "Ecommerce": 920, "B2B Services": 1120, "SMB": 640, "Enterprise": 1850}[segment]
        channel_aov = {"Email": 1.03, "Webinar": 1.12, "SEO / Blog": 1.00, "TikTok Ads": 0.88, "Google Ads": 0.96, "Afiliados": 0.92, "Facebook Ads": 0.93}[channel]
        product_multiplier = 2.35 if new_product_offer else 1.0
        webinar_multiplier = 1.08 if webinar_attended else 1.0
        aov = float(rng.lognormal(np.log(base_aov * channel_aov * product_multiplier * webinar_multiplier), 0.23))
        aov = round(np.clip(aov, 120, 5200), 2)
        revenue = round(converted * aov, 2)

        margin_base = 0.73
        margin_base += {"Email": 0.04, "Webinar": 0.03, "SEO / Blog": 0.02, "TikTok Ads": -0.015, "Google Ads": -0.01, "Afiliados": -0.04, "Facebook Ads": -0.02}[channel]
        margin_base += -0.030 if new_product_offer else 0
        gross_margin = round(float(np.clip(rng.normal(margin_base, 0.035), 0.52, 0.86)), 3)
        support_cost = 22 if converted else 0
        gross_profit = round(revenue * gross_margin, 2)
        contribution_profit = round(gross_profit - cost_attributed - support_cost, 2)
        days_to_close = int(max(0, rng.gamma(2.0, 3.0) - (2 if webinar_attended else 0))) if converted else ""

        rows.append(
            {
                "transaction_id": f"TX-{idx:06d}",
                "date": date.date().isoformat(),
                "month": date.strftime("%Y-%m"),
                "quarter": quarter,
                "channel": channel,
                "campaign_objective": campaign_objective,
                "customer_segment": segment,
                "lifecycle_stage": lifecycle_stage,
                "device": device,
                "geo_region": geo_region,
                "ad_budget_level": budget_level,
                "campaign_daily_spend_usd": round(campaign_daily_spend, 2),
                "cost_attributed_usd": round(cost_attributed, 2),
                "landing_variant": landing_variant,
                "cta_variant": cta_variant,
                "lead_magnet": lead_magnet,
                "checkout_simplified": checkout_simplified,
                "webinar_invited": webinar_invited,
                "webinar_attended": webinar_attended,
                "new_product_offer": new_product_offer,
                "lead_score": lead_score,
                "converted_to_sale": converted,
                "days_to_close": days_to_close,
                "aov_usd": aov if converted else 0.0,
                "revenue_usd": revenue,
                "gross_margin_pct": gross_margin,
                "gross_profit_usd": gross_profit,
                "contribution_profit_usd": contribution_profit,
            }
        )

    return pd.DataFrame(rows)


CATEGORICAL = [
    "channel",
    "campaign_objective",
    "customer_segment",
    "lifecycle_stage",
    "device",
    "geo_region",
    "ad_budget_level",
    "landing_variant",
    "cta_variant",
]

NUMERIC = [
    "campaign_daily_spend_usd",
    "cost_attributed_usd",
    "lead_magnet",
    "checkout_simplified",
    "webinar_invited",
    "webinar_attended",
    "new_product_offer",
    "lead_score",
]

FEATURES = CATEGORICAL + NUMERIC

# Proporcion de la ventana temporal reservada para validacion.
TEST_FRACTION = 0.25


def temporal_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corta por fecha, no al azar.

    Un train_test_split aleatorio sobre datos con fecha entrena con registros
    posteriores a los de validacion, asi que el modelo ve futuro al aprender y
    el AUC sale inflado. Aqui se entrena con la parte antigua de la ventana y se
    valida con la mas reciente, que es como se usara en produccion.

    El corte se devuelve desde una sola funcion para que las metricas del panel
    y las del pipeline no puedan desincronizarse.
    """
    ordered = df.sort_values("date", kind="stable")
    cut = int(len(ordered) * (1 - test_fraction))
    return ordered.iloc[:cut].copy(), ordered.iloc[cut:].copy()


def split_boundary(df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> dict[str, str]:
    """Fechas del corte, para poder mostrarlas y auditar la validacion."""
    train, test = temporal_split(df, test_fraction)
    return {
        "train_start": str(train["date"].min()),
        "train_end": str(train["date"].max()),
        "test_start": str(test["date"].min()),
        "test_end": str(test["date"].max()),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
    }


def build_conversion_model(df: pd.DataFrame) -> tuple[Pipeline, float]:
    preprocessor = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ]
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(max_iter=1000, C=0.8, random_state=SEED),
            ),
        ]
    )
    train, test = temporal_split(df)
    model.fit(train[FEATURES], train["converted_to_sale"])
    predicted = model.predict_proba(test[FEATURES])[:, 1]
    auc = roc_auc_score(test["converted_to_sale"], predicted)
    return model, float(auc)


def build_aov_model(df: pd.DataFrame) -> Pipeline:
    sold = df[df["converted_to_sale"] == 1].copy()
    preprocessor = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", StandardScaler(), NUMERIC),
        ]
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("regressor", HistGradientBoostingRegressor(max_iter=220, learning_rate=0.045, random_state=SEED)),
        ]
    )
    model.fit(sold[FEATURES], np.log1p(sold["aov_usd"]))
    return model


def predict_components(
    rows: pd.DataFrame,
    conversion_model: Pipeline,
    aov_model: Pipeline,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    p_sale = conversion_model.predict_proba(rows[FEATURES])[:, 1]
    aov = np.expm1(aov_model.predict(rows[FEATURES]))
    margin = rows["gross_margin_pct"].to_numpy()
    cost = rows["cost_attributed_usd"].to_numpy()
    return p_sale, aov, margin, cost


def estimate_historical_parameters(df: pd.DataFrame, conversion_model: Pipeline, aov_model: Pipeline) -> pd.DataFrame:
    rows = []

    def effect(name: str, base: pd.DataFrame, scenario: pd.DataFrame) -> None:
        p0, a0, m0, c0 = predict_components(base, conversion_model, aov_model)
        p1, a1, m1, c1 = predict_components(scenario, conversion_model, aov_model)
        value0 = p0 * a0 * m0 - c0
        value1 = p1 * a1 * m1 - c1
        delta = value1 - value0

        # El uplift medio por si solo no dice si el efecto sobrevive a otra muestra
        # de oportunidades. El intervalo si, y ademas deja ver cuando cruza el cero.
        try:
            from analitica_avanzada import intervalo_uplift

            ic = intervalo_uplift(delta, semilla=SEED)
        except Exception:
            ic = {}

        rows.append(
            {
                "parameter": name,
                "sample_size": len(base),
                "baseline_conversion": round(float(p0.mean()), 4),
                "scenario_conversion": round(float(p1.mean()), 4),
                "conversion_lift_pct": round(float((p1.mean() / p0.mean()) - 1), 4),
                "profit_lift_per_opportunity_usd": round(float(delta.mean()), 2),
                # None y no NaN: json.dumps escribe NaN, que no es JSON valido y
                # revienta el JSON.parse del navegador
                "profit_lift_ci_low_usd": round(float(ic["inferior"]), 2) if ic.get("inferior") is not None else None,
                "profit_lift_ci_high_usd": round(float(ic["superior"]), 2) if ic.get("superior") is not None else None,
                "profit_lift_significativo": bool(ic.get("significativo", False)),
                "source": "Estimado con contrafactual ML sobre historico sintetico",
            }
        )

    base = df.copy()
    funnel = base.copy()
    funnel["landing_variant"] = "landing_v2"
    funnel["cta_variant"] = "benefit_cta"
    funnel["lead_magnet"] = 1
    funnel["checkout_simplified"] = 1
    effect("funnel_full_optimized", base, funnel)

    paid = df[df["channel"].isin(["Facebook Ads", "Google Ads"])].copy()
    for level in ["low", "medium", "high", "saturated"]:
        level_df = paid[paid["ad_budget_level"] == level]
        if len(level_df) == 0:
            continue
        p, a, m, c = predict_components(level_df, conversion_model, aov_model)
        rows.append(
            {
                "parameter": f"paid_budget_{level}",
                "sample_size": len(level_df),
                "baseline_conversion": round(float(level_df["converted_to_sale"].mean()), 4),
                "scenario_conversion": round(float(p.mean()), 4),
                "conversion_lift_pct": "",
                "profit_lift_per_opportunity_usd": round(float((p * a * m - c).mean()), 2),
                "source": "Historico por nivel de inversion en ads",
            }
        )

    warm = df[(df["lifecycle_stage"] != "new_visitor") | (df["channel"].isin(["Email", "SEO / Blog", "Webinar"]))].copy()
    webinar = warm.copy()
    webinar["webinar_invited"] = 1
    webinar["webinar_attended"] = 1
    effect("webinar_attendance", warm, webinar)

    eligible = df[df["customer_segment"].isin(["Enterprise", "B2B Services", "Ecommerce"])].copy()
    product = eligible.copy()
    product["new_product_offer"] = 1
    effect("new_product_offer", eligible, product)

    return pd.DataFrame(rows)


def scenario_frames(base: pd.DataFrame, rng: np.random.Generator) -> dict[str, tuple[pd.DataFrame, float]]:
    scenarios: dict[str, tuple[pd.DataFrame, float]] = {}

    funnel = base.copy()
    funnel["landing_variant"] = "landing_v2"
    funnel["cta_variant"] = "benefit_cta"
    funnel["lead_magnet"] = 1
    funnel["checkout_simplified"] = 1
    scenarios["Optimizar la conversion del sitio"] = (funnel, 1200.0)

    paid_pool = base[base["channel"].isin(["Facebook Ads", "Google Ads"])].copy()
    extra_count = max(620, int(len(paid_pool) * 2.00))
    extra = paid_pool.sample(extra_count, replace=True, random_state=SEED).copy()
    extra["ad_budget_level"] = rng.choice(["high", "saturated"], size=extra_count, p=[0.80, 0.20])
    extra["campaign_daily_spend_usd"] = extra["campaign_daily_spend_usd"] * rng.normal(1.55, 0.12, extra_count)
    extra["cost_attributed_usd"] = extra["cost_attributed_usd"] * rng.normal(1.05, 0.12, extra_count)
    extra["lead_score"] = np.clip(extra["lead_score"] - rng.normal(4, 4, extra_count), 1, 99).round().astype(int)
    more_ads = pd.concat([base, extra], ignore_index=True)
    scenarios["Escalar paid social"] = (more_ads, 9000.0)

    warm = base.copy()
    candidate = (warm["lifecycle_stage"] != "new_visitor") | (warm["channel"].isin(["Email", "SEO / Blog", "Webinar"]))
    invited = candidate & (rng.random(len(warm)) < 0.62)
    attended = invited & (rng.random(len(warm)) < 0.34)
    warm.loc[invited, "webinar_invited"] = 1
    warm.loc[attended, "webinar_attended"] = 1
    scenarios["Reactivacion y remarketing"] = (warm, 2500.0)

    product = base.copy()
    eligible = product["customer_segment"].isin(["Enterprise", "B2B Services", "Ecommerce"])
    offered = eligible & (rng.random(len(product)) < 0.32)
    product.loc[offered, "new_product_offer"] = 1
    product.loc[offered, "cost_attributed_usd"] = product.loc[offered, "cost_attributed_usd"] + rng.lognormal(np.log(5.0), 0.35, offered.sum())
    scenarios["Abrir categoria nueva"] = (product, 12000.0)

    return scenarios


# Calibracion de los tres ruidos por decision, extraida del cuerpo del bucle
# para poder escalarla desde fuera y auditar de que depende la conclusion.
# (mu, sigma) de la lognormal de incertidumbre; valores y pesos del retraso de
# ejecucion; suelo y proporcion del ruido residual.
NOISE_PROFILES: dict[str, dict[str, object]] = {
    "Abrir categoria nueva": {
        "uncertainty": (-0.90, 1.38),
        "execution": ([0.10, 0.30, 0.76, 1.65, 3.40], [0.23, 0.25, 0.24, 0.18, 0.10]),
        "residual": (18_000, 0.34),
    },
    "Escalar paid social": {
        "uncertainty": (-0.08, 0.24),
        "execution": ([0.58, 0.82, 1.00, 1.16], [0.18, 0.30, 0.34, 0.18]),
        "residual": (16_000, 0.26),
    },
    "Reactivacion y remarketing": {
        "uncertainty": (0.0, 0.16),
        "execution": ([0.72, 0.94, 1.10, 1.22], [0.18, 0.36, 0.32, 0.14]),
        "residual": (4_000, 0.12),
    },
    "_default": {
        "uncertainty": (0.0, 0.07),
        "execution": ([0.88, 0.98, 1.05, 1.12], [0.14, 0.44, 0.30, 0.12]),
        "residual": (2_500, 0.06),
    },
}


def simulate_decisions(
    df: pd.DataFrame,
    conversion_model: Pipeline,
    aov_model: Pipeline,
    n_simulations: int = N_SIMULATIONS,
    progress_every: int = 0,
    progress_callback=None,
    pacing_total_seconds: float = 0.0,
    seed: int | None = None,
    noise_scales: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> pd.DataFrame:
    """`seed` permite repetir la realizacion con otros dados sin tocar los datos.

    `noise_scales` escala (incertidumbre, ejecucion, residual) de forma
    independiente: 1.0 es la calibracion elegida por el analista, 2.0 la duplica.
    Sirve para comprobar a partir de que exageracion cambia la recomendacion.
    """
    scale_unc, scale_exec, scale_res = noise_scales
    rng = np.random.default_rng(SEED if seed is None else seed)
    started_at = time.perf_counter()
    recent = df[df["date"] >= "2025-10-01"].copy()
    if len(recent) < 2500:
        recent = df.tail(4500).copy()

    base_size = min(3600, len(recent))
    base = recent.sample(base_size, replace=True, random_state=SEED).reset_index(drop=True)
    p0, a0, m0, c0 = predict_components(base, conversion_model, aov_model)
    base_expected_value = p0 * a0 * m0 - c0 - p0 * 22

    scenarios = scenario_frames(base, rng)
    precomputed = {}
    for decision, (scenario_df, fixed_cost) in scenarios.items():
        p, aov, margin, cost = predict_components(scenario_df, conversion_model, aov_model)
        expected_value = p * aov * margin - cost - p * 22
        precomputed[decision] = (scenario_df.reset_index(drop=True), fixed_cost, expected_value)

    results = []
    for sim in range(1, n_simulations + 1):
        idx = rng.integers(0, len(base), len(base))

        for decision, (scenario_df, fixed_cost, expected_value) in precomputed.items():
            if len(scenario_df) == len(base):
                raw_delta = float((expected_value[idx] - base_expected_value[idx]).sum())
            else:
                extra_value = expected_value[len(base) :]
                extra_idx = rng.integers(0, len(extra_value), len(extra_value))
                raw_delta = float(extra_value[extra_idx].sum())

            profile = NOISE_PROFILES.get(decision, NOISE_PROFILES["_default"])
            mu, sigma = profile["uncertainty"]
            valores, pesos = profile["execution"]
            suelo, proporcion = profile["residual"]

            uncertainty = rng.lognormal(mu, sigma * scale_unc)
            # el retraso se estira alrededor de 1.0 para no desplazar la media al escalarlo
            bruto = rng.choice(valores, p=pesos)
            execution_delay = 1.0 + (bruto - 1.0) * scale_exec
            residual_sd = max(suelo, abs(raw_delta) * proporcion) * scale_res

            incremental_profit = raw_delta * uncertainty * execution_delay - fixed_cost
            incremental_profit += rng.normal(0, residual_sd)
            results.append(
                {
                    "decision": decision,
                    "simulation": sim,
                    "incremental_profit_usd": round(incremental_profit, 2),
                    "roi": round(incremental_profit / fixed_cost, 4),
                }
            )

        if progress_callback is not None and progress_every and (sim % progress_every == 0 or sim == n_simulations):
            progress_callback(sim, n_simulations, results)
            if pacing_total_seconds > 0:
                target_elapsed = pacing_total_seconds * (sim / n_simulations)
                elapsed = time.perf_counter() - started_at
                wait_seconds = target_elapsed - elapsed
                if wait_seconds > 0:
                    time.sleep(wait_seconds)

    return pd.DataFrame(results)


def summarize_partial(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(
            columns=[
                "decision",
                "expected_profit_usd",
                "p10_usd",
                "p50_usd",
                "p90_usd",
                "probability_loss",
                "expected_roi",
            ]
        )
    return summarize(pd.DataFrame(results))


def write_live_dashboard(
    current_simulation: int,
    total_simulations: int,
    results: list[dict],
    output_path: Path = LIVE_DASHBOARD_PATH,
    status_path: Path = LIVE_STATUS_PATH,
    status_script_path: Path = LIVE_STATUS_SCRIPT_PATH,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_partial(results)
    leaderboard = summary.to_dict(orient="records")
    recent_runs = results[-16:]
    status = {
        "current_simulation": current_simulation,
        "total_simulations": total_simulations,
        "progress_pct": round(current_simulation / total_simulations * 100, 2),
        "is_running": current_simulation < total_simulations,
        "leaderboard": leaderboard,
        "recent_runs": recent_runs,
        "dashboard_path": LIVE_DASHBOARD_RELATIVE_PATH,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    status_script_path.write_text(
        "window.__MONTECARLO_STATUS__ = " + json.dumps(status, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    if _should_log_live_update(current_simulation, total_simulations):
        leader = leaderboard[0]["decision"] if leaderboard else None
        _debug_log(
            "live_dashboard_written",
            current_simulation=current_simulation,
            total_simulations=total_simulations,
            progress_pct=status["progress_pct"],
            is_running=status["is_running"],
            leader=leader,
            output_path=output_path.name,
            status_script_path=status_script_path.name,
        )

    colors = {
        "Optimizar la conversion del sitio": "#1fa971",
        "Reactivacion y remarketing": "#2f80ed",
        "Escalar paid social": "#d9531e",
        "Abrir categoria nueva": "#7c3aed",
    }
    initial_status = json.dumps(status, ensure_ascii=False)
    colors_json = json.dumps(colors, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang=\"es\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Monte Carlo Live</title>
<style>
:root {{ --bg:#ededed; --panel:#f2f2f2; --line:#dedddc; --cyan:#d9531e; --green:#1fa971; --amber:#d9531e; --pink:#7c3aed; --blue:#2f80ed; --text:#131313; --muted:#6c6c6c; --ghost:#b2b2b2; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Inter,-apple-system,Segoe UI,Arial,sans-serif; color:var(--text); background:var(--bg); overflow-x:hidden; }}
.shell {{ max-width:1500px; margin:0 auto; padding:24px; position:relative; }}
.hero,.panel,.card,.metric-chip {{ border:1px solid var(--line); background:var(--panel); border-radius:24px; box-shadow:0 12px 32px rgba(19,19,19,.06); }}
.hero {{ padding:24px; display:grid; grid-template-columns:1.15fr .85fr; gap:18px; position:relative; overflow:hidden; }}
.hero-copy,.hero-side {{ position:relative; z-index:1; }}
.hero h1 {{ margin:0; font-size:42px; text-transform:uppercase; letter-spacing:.08em; }}
.hero-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:18px; }}
.metric-chip {{ padding:14px 16px; }}
.metric-chip .label {{ font-size:11px; text-transform:uppercase; letter-spacing:.16em; color:var(--muted); }}
.metric-chip .value {{ margin-top:8px; font-size:26px; font-weight:800; color:var(--text); }}
.hero-side {{ display:grid; place-items:center; }}
.ring {{ width:230px; height:230px; border-radius:50%; position:relative; display:grid; place-items:center; background:conic-gradient(var(--cyan) 0deg, var(--cyan) 0deg, #e0e0de 0deg 360deg); transition:background .25s linear; }}
.ring:before {{ content:''; position:absolute; inset:18px; border-radius:50%; background:var(--panel); border:1px solid var(--line); }}
.ring:after {{ content:''; position:absolute; inset:34px; border-radius:50%; border:1px dashed rgba(120,201,227,.16); animation:rotate 16s linear infinite; }}
.ring-content {{ position:relative; text-align:center; z-index:1; }}
.ring-content .kicker {{ font-size:12px; letter-spacing:.18em; text-transform:uppercase; color:var(--muted); }}
.ring-content .big {{ font-size:54px; font-weight:800; line-height:1; color:var(--text); }}
.ring-content .sub {{ margin-top:8px; font-size:14px; color:var(--muted); }}
.cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:18px; }}
.card {{ padding:16px; position:relative; overflow:hidden; min-height:132px; }}
.card:after {{ content:''; position:absolute; inset:auto 0 0 0; height:3px; background:var(--accent,#d9531e);  }}
.kicker {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.16em; }}
.metric {{ margin-top:10px; font-size:31px; color:var(--text); font-weight:800; }}
.sub {{ margin-top:8px; color:var(--muted); font-size:13px; }}
.dashboard-grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:18px; margin-top:18px; }}
.panel {{ padding:18px; position:relative; overflow:hidden; }}
.panel h3 {{ margin:0 0 14px; font-size:15px; letter-spacing:.16em; text-transform:uppercase; color:var(--text); }}
.leaderboard-bars {{ display:grid; gap:12px; }}
.bar-row {{ display:grid; grid-template-columns:210px 1fr 90px; align-items:center; gap:12px; }}
.bar-track {{ height:18px; border-radius:999px; background:#e6e6e4; border:1px solid var(--line); overflow:hidden; position:relative; }}
.bar-fill {{ height:100%; border-radius:999px; position:relative; transition:width .32s ease-out; }}
.bar-value {{ text-align:right; font-weight:700; color:var(--text); }}
.radar-wrap {{ position:relative; min-height:340px; }}
.radar-grid {{ position:absolute; inset:0; background:radial-gradient(circle, rgba(19,19,19,.08) 0 1px, transparent 1px), linear-gradient(90deg, rgba(19,19,19,.06) 1px, transparent 1px), linear-gradient(180deg, rgba(19,19,19,.06) 1px, transparent 1px); background-size:28px 28px, 28px 28px, 28px 28px; mask-image:radial-gradient(circle at center, black 40%, transparent 88%); }}
.radar-sweep {{ position:absolute; inset:18px; border-radius:50%; background:conic-gradient(from 0deg, rgba(31,169,113,.20), transparent 55deg, transparent 360deg); animation:rotate 5s linear infinite; opacity:.6; }}
.radar-svg {{ position:relative; width:100%; height:340px; z-index:1; }}
.spark-grid {{ display:grid; gap:10px; }}
.spark-row {{ display:grid; grid-template-columns:220px 1fr 90px; gap:12px; align-items:center; }}
.spark-svg {{ width:100%; height:52px; display:block; }}
.spark-value {{ text-align:right; font-weight:700; }}
.telemetry-window {{ height:340px; overflow:hidden; position:relative; border:1px solid var(--line); border-radius:14px; background:var(--panel); }}
.telemetry-window:before, .telemetry-window:after {{ content:''; position:absolute; left:0; right:0; height:44px; z-index:2; pointer-events:none; }}
.telemetry-window:before {{ top:0; background:linear-gradient(180deg, var(--panel), rgba(242,242,242,0)); }}
.telemetry-window:after {{ bottom:0; background:linear-gradient(0deg, var(--panel), rgba(242,242,242,0)); }}
.telemetry-track {{ position:absolute; inset:0; padding:10px 12px 12px; display:grid; gap:8px; animation:none; --telemetry-duration:9s; }}
.telemetry-track.is-running {{ animation:telemetryDrift var(--telemetry-duration) linear infinite; }}
.telemetry-row {{ display:grid; grid-template-columns:92px 1.3fr 110px 74px; gap:10px; padding:10px 12px; border-radius:12px; background:#f7f7f6; border:1px solid var(--line); color:var(--text); transform:translateY(8px); opacity:0; animation:rowIn .45s ease forwards; }}
.telemetry-row:nth-child(odd) {{ background:#efefee; }}
.telemetry-row strong {{ color:var(--text); }}
.footer-note {{ margin-top:12px; color:#7eb7cb; font-size:12px; letter-spacing:.08em; text-transform:uppercase; }}
@keyframes rotate {{ from {{ transform:rotate(0deg); }} to {{ transform:rotate(360deg); }} }}
@keyframes sheen {{ from {{ transform:translateX(-120%); }} to {{ transform:translateX(120%); }} }}
@keyframes rowIn {{ to {{ opacity:1; transform:translateY(0); }} }}
@keyframes telemetryDrift {{ from {{ transform:translateY(0); }} to {{ transform:translateY(-35%); }} }}
@keyframes scan {{ from {{ transform:translateY(-4px); }} to {{ transform:translateY(4px); }} }}
@media (max-width:1200px) {{ .hero, .dashboard-grid {{ grid-template-columns:1fr; }} .cards {{ grid-template-columns:repeat(2,1fr); }} .bar-row, .spark-row {{ grid-template-columns:1fr; }} }}
@media (max-width:760px) {{ .cards {{ grid-template-columns:1fr; }} .ring {{ width:180px; height:180px; }} .hero h1 {{ font-size:32px; }} }}
</style>
</head>
<body>
<div class=\"shell\">
    <section class=\"hero\">
        <div class=\"hero-copy\">
            <div class=\"kicker\">Mission Control Monte Carlo</div>
            <h1>Simulacion en directo</h1>
            <div class=\"hero-grid\">
                <div class=\"metric-chip\"><div class=\"label\">Estado</div><div class=\"value\" id=\"hero-state\">En marcha</div></div>
                <div class=\"metric-chip\"><div class=\"label\">Lider</div><div class=\"value\" id=\"hero-leader\">-</div></div>
                <div class=\"metric-chip\"><div class=\"label\">ROI lider</div><div class=\"value\" id=\"hero-roi\">-</div></div>
            </div>
            <div class=\"footer-note\" id=\"hero-meta\">Esperando telemetria…</div>
        </div>
        <div class=\"hero-side\">
            <div class=\"ring\" id=\"progress-ring\">
                <div class=\"ring-content\">
                    <div class=\"kicker\">Progreso</div>
                    <div class=\"big\" id=\"progress-value\">0%</div>
                    <div class=\"sub\" id=\"progress-iteration\">Iteracion 0 de 0</div>
                </div>
            </div>
        </div>
    </section>
    <div class=\"cards\" id=\"leader-cards\"></div>
    <div class=\"dashboard-grid\">
        <section class=\"panel\">
            <h3>Radar riesgo / retorno</h3>
            <div class=\"radar-wrap\">
                <div class=\"radar-grid\"></div>
                <div class=\"radar-sweep\"></div>
                <svg class=\"radar-svg\" id=\"radar-svg\" viewBox=\"0 0 640 340\" preserveAspectRatio=\"none\"></svg>
            </div>
            <div class=\"footer-note\">Cuanto mas arriba, mayor beneficio esperado. Cuanto mas a la derecha, mayor probabilidad de perdida.</div>
        </section>
        <section class=\"panel\">
            <h3>Pulso reciente por decision</h3>
            <div class=\"spark-grid\" id=\"spark-grid\"></div>
        </section>
        <section class=\"panel\">
            <h3>Clasificacion en directo</h3>
            <div class=\"leaderboard-bars\" id=\"leaderboard-bars\"></div>
        </section>
        <section class=\"panel\">
            <h3>Telemetria en streaming</h3>
            <div class=\"telemetry-window\"><div class=\"telemetry-track\" id=\"telemetry-track\"></div></div>
        </section>
    </div>
</div>
<script>
window.__MONTECARLO_STATUS__ = {initial_status};
const COLORS = {colors_json};
const STATUS_SCRIPT_NAME = {json.dumps(status_script_path.name)};
const DEBUG_LOG_URL = '/api/debug-log';
let statusPollHandle = null;
let lastRenderedSignature = null;
let lastDebugMilestone = null;
let debugSequence = 0;

function reportDebug(event, details = {{}}, options = {{}}) {{
    try {{
        if (options.once) {{
            window.__LIVE_DEBUG_ONCE__ = window.__LIVE_DEBUG_ONCE__ || new Set();
            const key = JSON.stringify([event, details]);
            if (window.__LIVE_DEBUG_ONCE__.has(key)) return;
            window.__LIVE_DEBUG_ONCE__.add(key);
        }}
        const payload = JSON.stringify({{
            source: 'live_dashboard',
            event,
            sequence: ++debugSequence,
            href: window.location.href,
            ...details,
        }});
        if (navigator.sendBeacon) {{
            const blob = new Blob([payload], {{ type: 'application/json' }});
            navigator.sendBeacon(DEBUG_LOG_URL, blob);
            return;
        }}
        fetch(DEBUG_LOG_URL, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: payload,
            keepalive: true,
        }}).catch(() => {{}});
    }} catch (error) {{
    }}
}}

function reportStatusMilestone(status) {{
    const total = Number(status.total_simulations || 0);
    const current = Number(status.current_simulation || 0);
    const progress = Number(status.progress_pct || 0);
    let milestone = null;
    if (current <= 0) {{
        milestone = 'start';
    }} else if (!status.is_running) {{
        milestone = 'done';
    }} else {{
        const step = Math.max(1, Math.floor(total / 4));
        if (current % step === 0 || progress >= 99.9) {{
            milestone = `progress-${{current}}`;
        }}
    }}
    if (milestone && milestone !== lastDebugMilestone) {{
        lastDebugMilestone = milestone;
        const leader = status.leaderboard && status.leaderboard.length ? status.leaderboard[0].decision : null;
        reportDebug('live_status', {{
            milestone,
            current_simulation: current,
            total_simulations: total,
            progress_pct: progress,
            is_running: Boolean(status.is_running),
            leader,
        }});
    }}
}}

window.addEventListener('error', (event) => {{
    reportDebug('window_error', {{
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
    }});
}});

window.addEventListener('unhandledrejection', (event) => {{
    reportDebug('unhandled_rejection', {{
        reason: String(event.reason || 'unknown'),
    }});
}});

reportDebug('live_dashboard_boot', {{ status_script: STATUS_SCRIPT_NAME }}, {{ once: true }});

function statusSignature(status) {{
    const recent = status.recent_runs || [];
    const lastRecent = recent.length ? recent[recent.length - 1] : null;
    const leader = (status.leaderboard && status.leaderboard.length) ? status.leaderboard[0] : null;
    return [
        status.current_simulation || 0,
        status.total_simulations || 0,
        Number(status.progress_pct || 0).toFixed(2),
        status.is_running ? 1 : 0,
        leader ? leader.decision : 'none',
        leader ? Number(leader.expected_profit_usd || 0).toFixed(2) : '0.00',
        lastRecent ? lastRecent.simulation : 'none',
        lastRecent ? lastRecent.decision : 'none',
        lastRecent ? Number(lastRecent.incremental_profit_usd || 0).toFixed(2) : '0.00',
    ].join('|');
}}

function money(value) {{
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    return Number(value).toLocaleString('es-ES', {{ maximumFractionDigits: 0 }}) + ' USD';
}}

function shortMoney(value) {{
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    const abs = Math.abs(Number(value));
    if (abs >= 1000000) return (Number(value) / 1000000).toFixed(1) + 'M';
    if (abs >= 1000) return (Number(value) / 1000).toFixed(1) + 'k';
    return Number(value).toFixed(0);
}}

function pct(value) {{
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
    return (Number(value) * 100).toFixed(1) + '%';
}}

function setProgressRing(progressPct) {{
    const degrees = Math.max(0, Math.min(360, progressPct * 3.6));
    const ring = document.getElementById('progress-ring');
    ring.style.background = `conic-gradient(var(--cyan) 0deg, var(--green) ${{degrees}}deg, rgba(255,255,255,.06) ${{degrees}}deg 360deg)`;
}}

function renderCards(leaderboard) {{
    const root = document.getElementById('leader-cards');
    root.innerHTML = leaderboard.slice(0, 4).map((row) => `
        <section class="card" style="--accent:${{COLORS[row.decision] || '#d9531e'}}">
            <div class="kicker">Posicion ${{row.ranking}}</div>
            <div class="metric">${{shortMoney(row.expected_profit_usd)}}</div>
            <div class="sub">${{row.decision}}</div>
            <div class="sub">Perdida: ${{pct(row.probability_loss)}} · ROI: ${{Number(row.expected_roi).toFixed(2)}}x</div>
        </section>
    `).join('');
}}

function renderLeaderboardBars(leaderboard) {{
    const root = document.getElementById('leaderboard-bars');
    const maxValue = Math.max(...leaderboard.map((row) => Number(row.expected_profit_usd) || 0), 1);
    root.innerHTML = leaderboard.map((row) => {{
        const width = Math.max(6, (Number(row.expected_profit_usd) / maxValue) * 100);
        const color = COLORS[row.decision] || '#d9531e';
        return `
            <div class="bar-row">
                <div class="sub">${{row.decision}}</div>
                <div class="bar-track"><div class="bar-fill" style="width:${{width}}%; background:linear-gradient(90deg, ${{color}}, rgba(255,255,255,.15));"></div></div>
                <div class="bar-value">${{shortMoney(row.expected_profit_usd)}}</div>
            </div>
        `;
    }}).join('');
}}

function renderRadar(leaderboard) {{
    const svg = document.getElementById('radar-svg');
    const width = 640;
    const height = 340;
    const padX = 44;
    const padY = 24;
    const maxProfit = Math.max(...leaderboard.map((row) => Number(row.expected_profit_usd) || 0), 1);
    const axes = `
        <line x1="${{padX}}" y1="${{height - padY}}" x2="${{width - padX}}" y2="${{height - padY}}" stroke="rgba(140,185,206,.35)" />
        <line x1="${{padX}}" y1="${{height - padY}}" x2="${{padX}}" y2="${{padY}}" stroke="rgba(140,185,206,.35)" />
        <text x="${{width - padX}}" y="${{height - 8}}" fill="var(--muted)" font-size="11" text-anchor="end">Riesgo</text>
        <text x="12" y="${{padY + 12}}" fill="var(--muted)" font-size="11">Beneficio</text>
    `;
    const points = leaderboard.map((row) => {{
        const risk = Number(row.probability_loss) || 0;
        const profit = Number(row.expected_profit_usd) || 0;
        const x = padX + risk * (width - padX * 2);
        const y = height - padY - (profit / maxProfit) * (height - padY * 2);
        const color = COLORS[row.decision] || '#d9531e';
        return `
            <g>
                <circle cx="${{x}}" cy="${{y}}" r="8" fill="${{color}}" opacity="0.95">
                    <animate attributeName="r" values="7;10;7" dur="1.8s" repeatCount="indefinite" />
                </circle>
                <circle cx="${{x}}" cy="${{y}}" r="16" fill="${{color}}" opacity="0.16">
                    <animate attributeName="r" values="12;20;12" dur="1.8s" repeatCount="indefinite" />
                </circle>
                <text x="${{x + 12}}" y="${{y - 8}}" fill="#dff8ff" font-size="12">${{row.ranking}} · ${{row.decision}}</text>
            </g>
        `;
    }}).join('');
    svg.innerHTML = axes + points;
}}

function buildSparkline(points, color) {{
    if (!points.length) return '';
    const values = points.map((item) => Number(item.incremental_profit_usd) || 0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(1, max - min);
    const coords = values.map((value, index) => {{
        const x = (index / Math.max(1, values.length - 1)) * 300;
        const y = 44 - ((value - min) / span) * 36;
        return `${{x}},${{y}}`;
    }}).join(' ');
    return `
        <svg class="spark-svg" viewBox="0 0 300 52" preserveAspectRatio="none">
            <polyline fill="none" stroke="${{color}}" stroke-width="3" points="${{coords}}" stroke-linecap="round" stroke-linejoin="round"></polyline>
            <polyline fill="url(#fade-${{color.replace('#','')}})" opacity="0.18" points="0,52 ${{coords}} 300,52"></polyline>
            <defs>
                <linearGradient id="fade-${{color.replace('#','')}}" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="${{color}}"></stop>
                    <stop offset="100%" stop-color="${{color}}" stop-opacity="0"></stop>
                </linearGradient>
            </defs>
        </svg>
    `;
}}

function renderSparks(status) {{
    const root = document.getElementById('spark-grid');
    const grouped = new Map();
    (status.recent_runs || []).forEach((row) => {{
        if (!grouped.has(row.decision)) grouped.set(row.decision, []);
        grouped.get(row.decision).push(row);
    }});
    const rows = (status.leaderboard || []).map((entry) => {{
        const series = grouped.get(entry.decision) || [];
        const color = COLORS[entry.decision] || '#d9531e';
        const lastValue = series.length ? series[series.length - 1].incremental_profit_usd : entry.expected_profit_usd;
        return `
            <div class="spark-row">
                <div class="sub">${{entry.decision}}</div>
                ${{buildSparkline(series, color)}}
                <div class="spark-value" style="color:${{color}}">${{shortMoney(lastValue)}}</div>
            </div>
        `;
    }}).join('');
    root.innerHTML = rows;
}}

function renderTelemetry(status) {{
    const root = document.getElementById('telemetry-track');
    const recent = status.recent_runs || [];
    const tape = recent.concat(recent).slice(0, Math.max(12, recent.length * 2));
    const progress = Number(status.progress_pct || 0);
    const midBoost = 1 - Math.abs(progress - 50) / 50;
    const telemetryDuration = 11 - midBoost * 4.5;
    root.classList.toggle('is-running', Boolean(status.is_running));
    root.style.setProperty('--telemetry-duration', `${{telemetryDuration.toFixed(2)}}s`);
    root.innerHTML = tape.map((row, index) => `
        <div class="telemetry-row" style="animation-delay:${{(index % 10) * 0.03}}s">
            <div><strong>#${{row.simulation}}</strong></div>
            <div>${{row.decision}}</div>
            <div>${{money(row.incremental_profit_usd)}}</div>
            <div>${{Number(row.roi).toFixed(2)}}x</div>
        </div>
    `).join('');
}}

function render(status) {{
    const signature = statusSignature(status);
    if (signature === lastRenderedSignature) {{
        if (!status.is_running && statusPollHandle !== null) {{
            clearInterval(statusPollHandle);
            statusPollHandle = null;
        }}
        return;
    }}
    lastRenderedSignature = signature;
    reportStatusMilestone(status);
    const leaderboard = status.leaderboard || [];
    const best = leaderboard[0] || null;
    const progress = Number(status.progress_pct || 0);
    setProgressRing(progress);
    document.getElementById('progress-value').textContent = progress.toFixed(1) + '%';
    document.getElementById('progress-iteration').textContent = `Iteracion ${{Number(status.current_simulation || 0).toLocaleString('es-ES')}} de ${{Number(status.total_simulations || 0).toLocaleString('es-ES')}}`;
    document.getElementById('hero-state').textContent = status.is_running ? 'En marcha' : 'Completada';
    document.getElementById('hero-leader').textContent = best ? best.decision : '-';
    document.getElementById('hero-roi').textContent = best ? Number(best.expected_roi).toFixed(2) + 'x' : '-';
    document.getElementById('hero-meta').textContent = `Actualizado en iteracion ${{Number(status.current_simulation || 0).toLocaleString('es-ES')}} · archivo de estado: {status_path.name}`;
    renderCards(leaderboard);
    renderLeaderboardBars(leaderboard);
    renderRadar(leaderboard);
    renderSparks(status);
    renderTelemetry(status);
    if (!status.is_running && statusPollHandle !== null) {{
        clearInterval(statusPollHandle);
        statusPollHandle = null;
    }}
}}

function pullStatus() {{
    const previous = document.getElementById('status-loader');
    if (previous) previous.remove();
    const script = document.createElement('script');
    script.id = 'status-loader';
    script.src = STATUS_SCRIPT_NAME + '?ts=' + Date.now();
    script.onload = () => {{
        if (window.__MONTECARLO_STATUS__) render(window.__MONTECARLO_STATUS__);
    }};
    script.onerror = () => {{
        reportDebug('status_script_error', {{ script_src: script.src }});
    }};
    document.body.appendChild(script);
}}

render(window.__MONTECARLO_STATUS__);
if (window.__MONTECARLO_STATUS__ && window.__MONTECARLO_STATUS__.is_running) {{
    statusPollHandle = setInterval(pullStatus, 250);
}}
</script>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def summarize(simulations: pd.DataFrame) -> pd.DataFrame:
    summary = (
        simulations.groupby("decision")
        .agg(
            expected_profit_usd=("incremental_profit_usd", "mean"),
            p10_usd=("incremental_profit_usd", lambda x: np.percentile(x, 10)),
            p50_usd=("incremental_profit_usd", lambda x: np.percentile(x, 50)),
            p90_usd=("incremental_profit_usd", lambda x: np.percentile(x, 90)),
            probability_loss=("incremental_profit_usd", lambda x: (x < 0).mean()),
            expected_roi=("roi", "mean"),
        )
        .sort_values("expected_profit_usd", ascending=False)
        .reset_index()
    )
    summary.insert(0, "ranking", np.arange(1, len(summary) + 1))
    return summary


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(rows)


def evaluate(df: pd.DataFrame, params: pd.DataFrame, summary: pd.DataFrame, auc: float) -> tuple[bool, list[str]]:
    by_decision = summary.set_index("decision")
    param_idx = params.set_index("parameter")
    checks = [
        (
            "dataset_transaccional_20k",
            len(df) == N_ROWS
            and df["transaction_id"].is_unique
            and df["converted_to_sale"].between(0, 1).all()
            and df["date"].min() == "2024-01-01"
            and df["date"].max() <= "2026-04-30",
        ),
        (
            "parametros_emergen_del_historico",
            auc >= 0.70
            and param_idx.loc["funnel_full_optimized", "profit_lift_per_opportunity_usd"] > 8
            and param_idx.loc["webinar_attendance", "conversion_lift_pct"] > 0.20
            and param_idx.loc["paid_budget_saturated", "baseline_conversion"]
            < param_idx.loc["paid_budget_medium", "baseline_conversion"],
        ),
        (
            "conclusion_y_narrativa",
            # gana por el suelo, no por el techo: es lo que hace el caso
            summary.iloc[0]["decision"] == "Optimizar la conversion del sitio"
            and by_decision.loc[summary.iloc[0]["decision"], "p10_usd"] > 0
            and by_decision.loc[summary.iloc[0]["decision"], "probability_loss"] < 0.01
            # la apuesta de producto es la mas dispersa y la que mas pierde
            and by_decision.loc["Abrir categoria nueva", "probability_loss"] > 0.18
            and (
                by_decision.loc["Abrir categoria nueva", "p90_usd"]
                - by_decision.loc["Abrir categoria nueva", "p10_usd"]
            )
            == (by_decision["p90_usd"] - by_decision["p10_usd"]).max()
            and by_decision.loc["Escalar paid social", "probability_loss"] > 0.05,
        ),
    ]
    return all(result for _, result in checks), [f"{name}: {'PASS' if result else 'FAIL'}" for name, result in checks]


def write_report(df: pd.DataFrame, params: pd.DataFrame, summary: pd.DataFrame, auc: float, checks: list[str]) -> None:
    conversion = df["converted_to_sale"].mean()
    revenue = df["revenue_usd"].sum()
    profit = df["contribution_profit_usd"].sum()
    channel = (
        df.groupby("channel")
        .agg(
            registros=("transaction_id", "count"),
            conversion=("converted_to_sale", "mean"),
            revenue_usd=("revenue_usd", "sum"),
            contribution_profit_usd=("contribution_profit_usd", "sum"),
            coste_medio=("cost_attributed_usd", "mean"),
        )
        .reset_index()
    )
    channel["conversion"] = (channel["conversion"] * 100).round(1).astype(str) + "%"
    channel["revenue_usd"] = channel["revenue_usd"].round(0).astype(int)
    channel["contribution_profit_usd"] = channel["contribution_profit_usd"].round(0).astype(int)
    channel["coste_medio"] = channel["coste_medio"].round(2)

    pretty_summary = summary.copy()
    for col in ["expected_profit_usd", "p10_usd", "p50_usd", "p90_usd"]:
        pretty_summary[col] = pretty_summary[col].round(0).astype(int)
    pretty_summary["probability_loss"] = (pretty_summary["probability_loss"] * 100).round(1).astype(str) + "%"
    pretty_summary["expected_roi"] = pretty_summary["expected_roi"].round(1).astype(str) + "x"

    lines = [
        "# Evaluacion del dataset transaccional sintetico",
        "",
        "## Checks",
        *[f"- {check}" for check in checks],
        "",
        "## Baseline historico",
        f"- Registros: {len(df):,}",
        f"- Periodo: {df['date'].min()} a {df['date'].max()}",
        f"- Conversion media: {conversion:.1%}",
        f"- Revenue historico: {revenue:,.0f} USD",
        f"- Contribution profit historico: {profit:,.0f} USD",
        f"- AUC modelo de conversion: {auc:.3f}",
        "",
        "## Variables clave para estimar hipotesis",
        "- Cambios de funnel: landing_variant, cta_variant, lead_magnet, checkout_simplified.",
        "- Presion de ads: ad_budget_level, campaign_daily_spend_usd, cost_attributed_usd, lead_score.",
        "- Webinar: webinar_invited, webinar_attended.",
        "- Abrir categoria nueva: new_product_offer, customer_segment, aov_usd, gross_margin_pct.",
        "- Resultado de negocio: converted_to_sale, revenue_usd, gross_profit_usd, contribution_profit_usd.",
        "",
        "## Resumen por canal",
        markdown_table(channel),
        "",
        "## Parametros estimados desde historico",
        markdown_table(params),
        "",
        "## Simulacion Monte Carlo",
        markdown_table(pretty_summary),
        "",
        "## Lectura ejecutiva",
        "- Las hipotesis no se fijan como tabla externa: se estiman con contrafactuales del modelo entrenado sobre el historico.",
        "- Mejorar el funnel gana porque el historico contiene tests de landing, CTA, lead magnet y checkout que el modelo aprende como mejora de conversion.",
        "- Duplicar ads usa el patron historico de saturacion: cuando sube el nivel de inversion, crece el volumen pero baja la calidad media y sube el coste por oportunidad.",
        "- Webinar emerge como buena segunda opcion porque el historico contiene invitados/asistentes y el modelo aprende uplift en leads templados.",
        "- Abrir categoria nueva mantiene el P90 mas alto por ticket mayor, pero tambien mayor probabilidad de perdida por menor conversion, coste fijo y variabilidad de ejecucion.",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run_pipeline(
    n_simulations: int = N_SIMULATIONS,
    live_dashboard: bool = False,
    progress_every: int = 80,
    persist_outputs: bool = True,
    live_duration_seconds: float = 40.0,
) -> dict[str, object]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    pipeline_started_at = time.perf_counter()
    df = generate_dataset()
    if persist_outputs:
        df.to_csv(DATASET_PATH, index=False, encoding="utf-8")

    conversion_model, auc = build_conversion_model(df)
    aov_model = build_aov_model(df)

    params = estimate_historical_parameters(df, conversion_model, aov_model)
    if persist_outputs:
        params.to_csv(PARAMS_PATH, index=False, encoding="utf-8")

    progress_callback = None
    if live_dashboard:
        write_live_dashboard(0, n_simulations, [], LIVE_DASHBOARD_PATH, LIVE_STATUS_PATH)
        progress_callback = lambda current, total, results: write_live_dashboard(
            current,
            total,
            results,
            LIVE_DASHBOARD_PATH,
            LIVE_STATUS_PATH,
        )

    remaining_live_seconds = 0.0
    if live_dashboard and live_duration_seconds > 0:
        elapsed_before_simulation = time.perf_counter() - pipeline_started_at
        remaining_live_seconds = max(0.0, live_duration_seconds - elapsed_before_simulation)

    simulations = simulate_decisions(
        df,
        conversion_model,
        aov_model,
        n_simulations=n_simulations,
        progress_every=progress_every,
        progress_callback=progress_callback,
        pacing_total_seconds=remaining_live_seconds,
    )
    if persist_outputs:
        simulations.to_csv(SIMULATIONS_PATH, index=False, encoding="utf-8")

    summary = summarize(simulations)
    if persist_outputs:
        summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8")

    passed, checks = evaluate(df, params, summary, auc)
    if persist_outputs:
        write_report(df, params, summary, auc, checks)

    if live_dashboard:
        write_live_dashboard(n_simulations, n_simulations, simulations.to_dict(orient="records"), LIVE_DASHBOARD_PATH, LIVE_STATUS_PATH)

    return {
        "passed": passed,
        "checks": checks,
        "auc": auc,
        "dataset_path": DATASET_PATH,
        "params_path": PARAMS_PATH,
        "simulations_path": SIMULATIONS_PATH,
        "summary_path": SUMMARY_PATH,
        "report_path": REPORT_PATH,
        "dashboard_path": LIVE_DASHBOARD_PATH,
        "summary": summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulacion Monte Carlo end-to-end para el caso de negocio")
    parser.add_argument("--simulations", type=int, default=N_SIMULATIONS, help="Numero de iteraciones Monte Carlo")
    parser.add_argument("--live-dashboard", action="store_true", help="Genera un dashboard vivo durante la simulacion")
    parser.add_argument("--progress-every", type=int, default=80, help="Frecuencia de actualizacion del dashboard")
    parser.add_argument("--live-duration-seconds", type=float, default=40.0, help="Duracion objetivo del modo live en segundos")
    parser.add_argument("--no-persist", action="store_true", help="No sobrescribir los CSV finales")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_pipeline(
        n_simulations=args.simulations,
        live_dashboard=args.live_dashboard,
        progress_every=args.progress_every,
        persist_outputs=not args.no_persist,
        live_duration_seconds=args.live_duration_seconds,
    )

    print("PASS" if result["passed"] else "FAIL")
    print(f"dataset={result['dataset_path']}")
    print(f"params={result['params_path']}")
    print(f"summary={result['summary_path']}")
    print(f"report={result['report_path']}")
    print(f"dashboard={result['dashboard_path']}")
    print(f"auc={result['auc']:.3f}")
    print(result["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
