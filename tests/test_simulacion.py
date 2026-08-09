"""Pruebas del motor.

No cubren todo. Cubren las cosas que si se rompen invalidan el caso entero:
que el corte sea temporal, que la descarga profunda destruya margen y que el
guardarrail retire las frases que contradicen las cifras.
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
    aplicar_profundidad,
    generate_dataset,
    scenario_frames,
    temporal_split,
)


@pytest.fixture(scope="module")
def df():
    return generate_dataset()


def test_dataset_tiene_forma_esperada(df):
    assert len(df) == 20000
    assert df["ventana_id"].is_unique
    assert df["cubrio_degradacion"].isin([0, 1]).all()


def test_sin_nulos_en_las_features(df):
    # un NaN aqui revienta LogisticRegression en tiempo de entrenamiento
    assert df[FEATURES].isna().sum().sum() == 0


def test_no_hay_fuga_del_objetivo(df):
    # estas columnas se calculan DESPUES de saber el resultado
    posteriores = {
        "energia_mwh",
        "ingreso_usd",
        "margen_bruto_usd",
        "margen_neto_usd",
        "latencia_respuesta_min",
    }
    assert posteriores & set(FEATURES) == set()


def test_el_corte_es_temporal_no_aleatorio(df):
    train, test = temporal_split(df)
    assert train["date"].max() <= test["date"].min()
    esperado = int(len(df) * TEST_FRACTION)
    assert abs(len(test) - esperado) < len(df) * 0.02


def test_los_ciclos_solo_crecen(df):
    assert df["ciclos_acumulados"].is_monotonic_increasing
    # una bateria de red hace del orden de 1 ciclo al dia; en 2,3 anios no
    # deberia pasar de unos 1200
    assert 400 < df["ciclos_acumulados"].max() < 1500


def test_la_descarga_profunda_destruye_margen(df):
    por_profundidad = df.groupby("profundidad_descarga")["margen_neto_usd"].mean()
    assert por_profundidad["profunda"] < por_profundidad["conservadora"]


def test_la_profunda_mueve_mas_energia_pero_deja_menos(df):
    g = df.groupby("profundidad_descarga").agg(
        energia=("energia_mwh", "sum"), neto=("margen_neto_usd", "sum")
    )
    assert g.loc["profunda", "energia"] > g.loc["conservadora", "energia"]
    assert g.loc["profunda", "neto"] < g.loc["conservadora", "neto"]


def test_aplicar_profundidad_arrastra_el_coste(df):
    base = df.head(500)
    profunda = aplicar_profundidad(base, "profunda")
    solo_conservadoras = base["profundidad_descarga"] == "conservadora"
    assert (
        profunda.loc[solo_conservadoras, "coste_degradacion_usd"].sum()
        > base.loc[solo_conservadoras, "coste_degradacion_usd"].sum()
    )


def test_los_escenarios_no_meten_nulos(df):
    rng = np.random.default_rng(SEED)
    for nombre, (frame, coste) in scenario_frames(df, rng).items():
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
                "decision": "Arbitraje agresivo",
                "expected_profit_usd": 40000,
                "p10_usd": -33868,
                "probability_loss": 0.356,
            }
        ]
        informe = {
            "headline": "Arbitraje agresivo tiene suelo positivo en P10",
            "reasons": ["El suelo es positivo y la perdida es practicamente nula"],
        }
        limpio = coherencia_informe(informe, ranking)
        assert limpio["incidencias"], "deberia haber detectado la contradiccion"

    def test_deja_pasar_lo_que_si_cuadra(self):
        ranking = [
            {
                "decision": "Ventana conservadora",
                "expected_profit_usd": 56271,
                "p10_usd": 45156,
                "probability_loss": 0.0,
            }
        ]
        informe = {
            "headline": "Ventana conservadora mantiene un suelo positivo en P10",
            "reasons": ["El P10 se queda en 45.156 USD"],
        }
        limpio = coherencia_informe(informe, ranking)
        assert not limpio["incidencias"]


def test_el_intervalo_bootstrap_contiene_la_media():
    rng = np.random.default_rng(7)
    muestra = rng.normal(25, 6, 4000)
    ic = intervalo_uplift(muestra, semilla=7)
    assert ic["inferior"] < muestra.mean() < ic["superior"]
