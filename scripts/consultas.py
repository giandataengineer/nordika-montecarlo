"""Capa SQL sobre el historico de despacho.

Las agregaciones del informe estaban en pandas. Pasarlas a SQL tiene dos
razones: la primera es que un GROUP BY con ventanas se lee mejor en SQL que
encadenando .groupby().agg().reset_index(); la segunda es que el dia que el
historico no quepa en memoria, estas mismas consultas corren contra Postgres
cambiando la conexion y nada mas.

DuckDB lee el CSV directamente, sin cargar ni copiar, asi que no hay paso de
ingesta que mantener.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET = PROJECT_ROOT / "datos" / "dataset_ventas_transaccional_sintetico_es.csv"


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE VIEW despacho AS SELECT * FROM read_csv_auto('{DATASET}')")
    return con


# Margen por bloque horario. Es la consulta que responde donde esta el dinero:
# la punta de noche concentra el diferencial, el valle solar lo destruye.
MARGEN_POR_BLOQUE = """
SELECT
    bloque_horario,
    count(*)                                    AS ventanas,
    round(avg(cubrio_degradacion), 4)           AS tasa_cobertura,
    round(sum(energia_mwh), 1)                  AS energia_mwh,
    round(avg(diferencial_usd_mwh), 2)          AS diferencial_medio,
    round(avg(coste_degradacion_usd), 2)        AS degradacion_media,
    round(sum(margen_neto_usd), 2)              AS margen_neto
FROM despacho
GROUP BY bloque_horario
ORDER BY margen_neto DESC
"""

# El mecanismo del caso en una sola consulta: la descarga profunda mueve mas
# energia, factura mas y deja menos.
COMPARATIVA_PROFUNDIDAD = """
SELECT
    profundidad_descarga,
    count(*)                                AS ventanas,
    round(sum(energia_mwh), 1)              AS energia_mwh,
    round(avg(margen_bruto_usd), 2)         AS bruto_medio,
    round(avg(coste_degradacion_usd), 2)    AS desgaste_medio,
    round(avg(margen_neto_usd), 2)          AS neto_medio,
    round(sum(margen_neto_usd), 2)          AS neto_total
FROM despacho
GROUP BY profundidad_descarga
ORDER BY neto_total DESC
"""

# Evolucion mensual con media movil de tres meses. La funcion de ventana es
# la razon principal por la que esto vive en SQL y no en pandas.
EVOLUCION_MENSUAL = """
WITH por_mes AS (
    SELECT
        month                                       AS mes,
        sum(margen_neto_usd)                        AS margen,
        sum(energia_mwh)                            AS energia,
        avg(precio_spot_usd_mwh)                    AS precio_medio,
        max(ciclos_acumulados)                      AS ciclos
    FROM despacho
    GROUP BY month
)
SELECT
    mes,
    round(margen, 2)        AS margen_neto,
    round(energia, 1)       AS energia_mwh,
    round(precio_medio, 2)  AS precio_medio,
    round(ciclos, 1)        AS ciclos_acumulados,
    round(avg(margen) OVER (ORDER BY mes ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS margen_media_movil_3m
FROM por_mes
ORDER BY mes
"""

# Las horas que de verdad pagan el ano. Sirve para enseñar que el ingreso no
# esta repartido: se concentra en muy pocas ventanas.
CONCENTRACION_DEL_MARGEN = """
WITH rentables AS (
    SELECT margen_neto_usd
    FROM despacho
    WHERE cubrio_degradacion = 1 AND margen_neto_usd > 0
),
acumulado AS (
    SELECT
        row_number() OVER (ORDER BY margen_neto_usd DESC)               AS puesto,
        count(*)     OVER ()                                            AS total,
        sum(margen_neto_usd) OVER (ORDER BY margen_neto_usd DESC)       AS margen_acum,
        sum(margen_neto_usd) OVER ()                                    AS margen_total
    FROM rentables
)
SELECT
    tramo,
    max(pct_margen) AS pct_del_margen
FROM (
    SELECT
        CASE
            WHEN puesto <= total * 0.01 THEN 'top 1%'
            WHEN puesto <= total * 0.05 THEN 'top 5%'
            WHEN puesto <= total * 0.10 THEN 'top 10%'
            WHEN puesto <= total * 0.25 THEN 'top 25%'
            ELSE 'resto'
        END AS tramo,
        round(100.0 * margen_acum / margen_total, 1) AS pct_margen
    FROM acumulado
)
GROUP BY tramo
ORDER BY pct_del_margen
"""


def margen_por_bloque() -> pd.DataFrame:
    with _con() as con:
        return con.execute(MARGEN_POR_BLOQUE).df()


def comparativa_profundidad() -> pd.DataFrame:
    with _con() as con:
        return con.execute(COMPARATIVA_PROFUNDIDAD).df()


def evolucion_mensual() -> pd.DataFrame:
    with _con() as con:
        return con.execute(EVOLUCION_MENSUAL).df()


def concentracion_del_margen() -> pd.DataFrame:
    with _con() as con:
        return con.execute(CONCENTRACION_DEL_MARGEN).df()


def _autocomprobacion() -> None:
    bloques = margen_por_bloque()
    assert len(bloques) == 6, "faltan bloques horarios"
    assert bloques.iloc[0]["margen_neto"] > bloques.iloc[-1]["margen_neto"]

    prof = comparativa_profundidad()
    assert set(prof["profundidad_descarga"]) == {"conservadora", "profunda"}
    # el caso entero depende de esto
    fila_prof = prof[prof.profundidad_descarga == "profunda"].iloc[0]
    fila_cons = prof[prof.profundidad_descarga == "conservadora"].iloc[0]
    assert fila_prof["energia_mwh"] > fila_cons["energia_mwh"]
    assert fila_prof["neto_medio"] < fila_cons["neto_medio"]

    meses = evolucion_mensual()
    assert len(meses) >= 24
    assert meses["ciclos_acumulados"].is_monotonic_increasing

    print("consultas: todas las comprobaciones pasan")


if __name__ == "__main__":
    for titulo, fn in [
        ("Margen por bloque horario", margen_por_bloque),
        ("Conservadora contra profunda", comparativa_profundidad),
        ("Concentracion del margen", concentracion_del_margen),
    ]:
        print(f"\n{titulo}")
        print(fn().to_string(index=False))
    print()
    _autocomprobacion()
