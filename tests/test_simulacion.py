"""Pruebas del motor.

No cubren todo. Cubren lo que si se rompe invalida el caso entero: que el
corte sea temporal, que la saturacion publicitaria aparezca en los datos, y
que el guardarrail retire las frases que contradicen las cifras.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from analitica_avanzada import coherencia_informe, intervalo_uplift
from simulacion_montecarlo import (
    FEATURES,
    SEED,
    TEST_FRACTION,
    generate_dataset,
    scenario_frames,
    temporal_split,
)


@pytest.fixture(scope="module")
def df():
    return generate_dataset()


def test_dataset_tiene_forma_esperada(df):
    assert len(df) == 20000
    assert df["transaction_id"].is_unique
    assert df["converted_to_sale"].isin([0, 1]).all()


def test_sin_nulos_en_las_features(df):
    # un NaN aqui revienta LogisticRegression en tiempo de entrenamiento
    assert df[FEATURES].isna().sum().sum() == 0


def test_no_hay_fuga_del_objetivo(df):
    # estas columnas se calculan DESPUES de saber si convirtio
    posteriores = {
        "aov_usd",
        "revenue_usd",
        "gross_profit_usd",
        "contribution_profit_usd",
        "days_to_close",
    }
    assert posteriores & set(FEATURES) == set()


def test_el_corte_es_temporal_no_aleatorio(df):
    train, test = temporal_split(df)
    assert train["date"].max() <= test["date"].min()
    esperado = int(len(df) * TEST_FRACTION)
    assert abs(len(test) - esperado) < len(df) * 0.02


def test_tiktok_es_canal_pagado(df):
    # el caso trata sobre reparto de inversion: TikTok tiene que tener presupuesto
    tiktok = df[df["channel"] == "TikTok Ads"]
    assert len(tiktok) > 1000
    assert (tiktok["ad_budget_level"] != "organic_or_owned").all()
    assert tiktok["campaign_daily_spend_usd"].sum() > 0


def test_la_saturacion_degrada_la_calidad(df):
    pagados = df[df["ad_budget_level"] != "organic_or_owned"]
    calidad = pagados.groupby("ad_budget_level")["lead_score"].mean()
    conversion = pagados.groupby("ad_budget_level")["converted_to_sale"].mean()
    # el hallazgo central: al saturar, la calidad y la conversion caen
    assert calidad["saturated"] < calidad["medium"]
    assert conversion["saturated"] < conversion["medium"]


def test_saturar_destruye_margen(df):
    pagados = df[df["ad_budget_level"] != "organic_or_owned"]
    margen = pagados.groupby("ad_budget_level")["contribution_profit_usd"].mean()
    coste = pagados.groupby("ad_budget_level")["cost_attributed_usd"].mean()
    assert coste["saturated"] > coste["low"]
    assert margen["saturated"] < margen["medium"] * 0.5


def test_los_escenarios_no_meten_nulos(df):
    rng = np.random.default_rng(SEED)
    esperados = {
        "Optimizar la conversión del sitio",
        "Escalar paid social",
        "Reactivación y remarketing",
        "Abrir categoría nueva",
    }
    escenarios = scenario_frames(df, rng)
    assert set(escenarios) == esperados
    for nombre, (frame, coste) in escenarios.items():
        assert frame[FEATURES].isna().sum().sum() == 0, nombre
        assert coste > 0, nombre


def test_reproducible_con_la_misma_semilla():
    a = generate_dataset()
    b = generate_dataset()
    pd.testing.assert_frame_equal(a, b)


class TestGuardarrail:
    def test_retira_la_frase_que_contradice_el_p10(self):
        ranking = [
            {
                "decision": "Abrir categoría nueva",
                "expected_profit_usd": 4582,
                "p10_usd": -29826,
                "probability_loss": 0.568,
            }
        ]
        informe = {
            "headline": "Abrir categoría nueva tiene suelo positivo en P10",
            "reasons": ["El suelo es positivo y la perdida es practicamente nula"],
        }
        limpio = coherencia_informe(informe, ranking)
        assert limpio["incidencias"], "deberia haber detectado la contradiccion"

    def test_deja_pasar_lo_que_si_cuadra(self):
        ranking = [
            {
                "decision": "Optimizar la conversión del sitio",
                "expected_profit_usd": 54119,
                "p10_usd": 46022,
                "probability_loss": 0.0,
            }
        ]
        informe = {
            "headline": "Optimizar la conversión del sitio mantiene un suelo positivo en P10",
            "reasons": ["El P10 se queda en 46.022 USD"],
        }
        limpio = coherencia_informe(informe, ranking)
        assert not limpio["incidencias"]


def test_el_intervalo_bootstrap_contiene_la_media():
    rng = np.random.default_rng(7)
    muestra = rng.normal(25, 6, 4000)
    ic = intervalo_uplift(muestra, semilla=7)
    assert ic["inferior"] < muestra.mean() < ic["superior"]
