"""Capa SQL sobre el historico de captacion.

Las agregaciones del informe estaban en pandas. En SQL se leen mejor, sobre
todo las de ventana, y el dia que el historico no quepa en memoria estas
mismas consultas corren contra Postgres cambiando la conexion.

DuckDB lee el CSV directamente, sin paso de ingesta que mantener.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "datos" / "dataset_ventas_transaccional_sintetico_es.csv"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW oportunidades AS SELECT * FROM read_csv_auto('{DATASET}')")
    return con


# Rentabilidad por canal. Es la consulta que responde de donde sale el margen
# y cual de los canales pagados esta comprando volumen caro.
RENTABILIDAD_POR_CANAL = """
SELECT
    channel                                             AS canal,
    count(*)                                            AS oportunidades,
    round(avg(converted_to_sale), 4)                    AS tasa_conversion,
    round(avg(cost_attributed_usd), 2)                  AS coste_medio,
    round(sum(cost_attributed_usd), 2)                  AS inversion,
    round(sum(revenue_usd), 2)                          AS ingreso,
    round(sum(contribution_profit_usd), 2)              AS margen,
    round(sum(revenue_usd) / nullif(sum(cost_attributed_usd), 0), 2) AS roas
FROM oportunidades
GROUP BY channel
ORDER BY margen DESC
"""

# La curva de saturacion: el hallazgo central del caso. Al subir de nivel de
# inversion crece el volumen y cae la calidad, hasta que el margen se da vuelta.
CURVA_DE_SATURACION = """
SELECT
    ad_budget_level                                     AS nivel_inversion,
    count(*)                                            AS oportunidades,
    round(avg(converted_to_sale), 4)                    AS tasa_conversion,
    round(avg(lead_score), 1)                           AS calidad_media,
    round(avg(cost_attributed_usd), 2)                  AS coste_por_oportunidad,
    round(avg(contribution_profit_usd), 2)              AS margen_por_oportunidad
FROM oportunidades
WHERE ad_budget_level <> 'organic_or_owned'
GROUP BY ad_budget_level
ORDER BY coste_por_oportunidad
"""

# Evolucion mensual con media movil de tres meses. La funcion de ventana es la
# razon principal por la que esto vive en SQL y no en pandas.
EVOLUCION_MENSUAL = """
WITH por_mes AS (
    SELECT
        month                       AS mes,
        sum(contribution_profit_usd) AS margen,
        sum(cost_attributed_usd)     AS inversion,
        sum(revenue_usd)             AS ingreso,
        avg(converted_to_sale)       AS conversion
    FROM oportunidades
    GROUP BY month
)
SELECT
    mes,
    round(margen, 2)        AS margen,
    round(inversion, 2)     AS inversion,
    round(conversion, 4)    AS tasa_conversion,
    round(ingreso / nullif(inversion, 0), 2) AS roas,
    round(avg(margen) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS margen_media_movil_3m
FROM por_mes
ORDER BY mes
"""

# Concentracion del margen: cuantas oportunidades pagan de verdad el ano.
CONCENTRACION_DEL_MARGEN = """
WITH rentables AS (
    SELECT contribution_profit_usd
    FROM oportunidades
    WHERE converted_to_sale = 1 AND contribution_profit_usd > 0
),
acumulado AS (
    SELECT
        row_number() OVER (ORDER BY contribution_profit_usd DESC)         AS puesto,
        count(*)     OVER ()                                              AS total,
        sum(contribution_profit_usd) OVER (ORDER BY contribution_profit_usd DESC) AS acum,
        sum(contribution_profit_usd) OVER ()                              AS margen_total
    FROM rentables
)
SELECT tramo, max(pct_margen) AS pct_del_margen
FROM (
    SELECT
        CASE
            WHEN puesto <= total * 0.01 THEN 'top 1%'
            WHEN puesto <= total * 0.05 THEN 'top 5%'
            WHEN puesto <= total * 0.10 THEN 'top 10%'
            WHEN puesto <= total * 0.25 THEN 'top 25%'
            ELSE 'resto'
        END AS tramo,
        round(100.0 * acum / margen_total, 1) AS pct_margen
    FROM acumulado
)
GROUP BY tramo
ORDER BY pct_del_margen
"""


def rentabilidad_por_canal() -> pd.DataFrame:
    with _con() as con:
        return con.execute(RENTABILIDAD_POR_CANAL).df()


def curva_de_saturacion() -> pd.DataFrame:
    with _con() as con:
        return con.execute(CURVA_DE_SATURACION).df()


def evolucion_mensual() -> pd.DataFrame:
    with _con() as con:
        return con.execute(EVOLUCION_MENSUAL).df()


def concentracion_del_margen() -> pd.DataFrame:
    with _con() as con:
        return con.execute(CONCENTRACION_DEL_MARGEN).df()


def _autocomprobacion() -> None:
    canales = rentabilidad_por_canal()
    assert len(canales) == 7, "faltan canales"
    assert canales.iloc[0]["margen"] > canales.iloc[-1]["margen"]

    saturacion = curva_de_saturacion()
    assert len(saturacion) == 4
    # el caso entero depende de esto: al saturar, la conversion cae
    barato = saturacion.iloc[0]
    caro = saturacion.iloc[-1]
    assert caro["coste_por_oportunidad"] > barato["coste_por_oportunidad"]
    assert caro["tasa_conversion"] < barato["tasa_conversion"]

    meses = evolucion_mensual()
    assert len(meses) >= 24

    print("consultas: todas las comprobaciones pasan")


if __name__ == "__main__":
    for titulo, fn in [
        ("Rentabilidad por canal", rentabilidad_por_canal),
        ("Curva de saturacion publicitaria", curva_de_saturacion),
        ("Concentracion del margen", concentracion_del_margen),
    ]:
        print(f"\n{titulo}")
        print(fn().to_string(index=False))
    print()
    _autocomprobacion()
