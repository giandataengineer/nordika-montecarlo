"""Capa SQL sobre el histórico de captación.

Las agregaciones del informe estaban en pandas. En SQL se leen mejor, sobre
todo las de ventana, y el dia que el histórico no quepa en memoria estas
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


SQL_DIR = PROJECT_ROOT / "sql"


def _leer(nombre: str) -> str:
    """Las consultas viven en sql/*.sql, no incrustadas aqui.

    Asi se revisan en un editor de SQL, se versionan por separado y el dia que
    haya que llevarlas a Postgres o a dbt se mueve el fichero y ya.
    """
    return (SQL_DIR / nombre).read_text(encoding="utf-8")


RENTABILIDAD_POR_CANAL = _leer("01_rentabilidad_por_canal.sql")
CURVA_DE_SATURACION = _leer("02_curva_de_saturacion.sql")
EVOLUCION_MENSUAL = _leer("03_evolucion_mensual.sql")
CONCENTRACION_DEL_MARGEN = _leer("04_concentracion_del_margen.sql")


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
    # el caso entero depende de esto: al saturar, la conversión cae
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
        ("Curva de saturación publicitaria", curva_de_saturacion),
        ("Concentración del margen", concentracion_del_margen),
    ]:
        print(f"\n{titulo}")
        print(fn().to_string(index=False))
    print()
    _autocomprobacion()
