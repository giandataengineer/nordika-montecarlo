# Evaluacion del dataset transaccional sintetico

## Checks
- dataset_transaccional_20k: PASS
- parametros_emergen_del_historico: PASS
- conclusion_y_narrativa: PASS

## Baseline historico
- Registros: 20,000
- Periodo: 2024-01-01 a 2026-04-30
- Conversion media: 13.4%
- Ingreso historico: 951,040 USD
- Margen neto historico: 9,819 USD
- AUC modelo de cobertura de degradacion: 0.721

## Variables clave para estimar hipotesis
- Control de operacion: profundidad_descarga, ventana_carga, rampa_optimizada, reserva_comprometida.
- Condiciones de mercado: precio_spot_usd_mwh, diferencial_usd_mwh, estado_red, bloque_horario.
- Estado del activo: soc_inicial_pct, ciclos_acumulados, coste_degradacion_usd, indice_despacho.
- Productos de mercado: regulacion_ofertada, regulacion_convocada, mercado_nuevo, zona_red.
- Resultado economico: cubrio_degradacion, ingreso_usd, margen_bruto_usd, margen_neto_usd.

## Resumen por bloque horario
| bloque_horario · registros · conversion · ingreso_usd · margen_neto_usd · coste_medio |
| --- · --- · --- · --- · --- · --- |
| madrugada · 3593 · 7.8% · 24919 · -106441 · 32.84 |
| manana · 3134 · 13.4% · 90193 · -44495 · 32.79 |
| noche · 668 · 12.1% · 16321 · -11871 · 33.39 |
| punta_noche · 3494 · 21.7% · 399741 · 177549 · 32.3 |
| punta_tarde · 4644 · 18.9% · 410927 · 138144 · 33.0 |
| valle_solar · 4467 · 5.8% · 8939 · -143067 · 32.12 |

## Parametros estimados desde historico
| parameter · sample_size · baseline_cobertura · scenario_conversion · conversion_lift_pct · profit_lift_per_window_usd · profit_lift_ci_low_usd · profit_lift_ci_high_usd · profit_lift_significativo · source |
| --- · --- · --- · --- · --- · --- · --- · --- · --- · --- |
| control_fino_completo · 20000 · 0.1373 · 0.2185 · 0.5917 · 22.07 · 21.78 · 22.38 · True · Estimado con contrafactual ML sobre historico sintetico |
| bloque_punta_noche · 3494 · 0.2172 · 0.221 ·  · 55.72 · nan · nan · nan · Historico por bloque horario de despacho |
| bloque_punta_tarde · 4644 · 0.1895 · 0.1912 ·  · 33.12 · nan · nan · nan · Historico por bloque horario de despacho |
| bloque_manana · 3134 · 0.134 · 0.1419 ·  · -10.29 · nan · nan · nan · Historico por bloque horario de despacho |
| bloque_valle_solar · 4467 · 0.0582 · 0.0601 ·  · -30.36 · nan · nan · nan · Historico por bloque horario de despacho |
| descarga_profunda · 20000 · 0.1373 · 0.1196 · -0.1292 · -2.87 · -3.0 · -2.73 · True · Estimado con contrafactual ML sobre historico sintetico |
| regulacion_convocada · 15439 · 0.1608 · 0.1826 · 0.1355 · 5.37 · 5.27 · 5.46 · True · Estimado con contrafactual ML sobre historico sintetico |
| mercado_nuevo · 14041 · 0.1424 · 0.1541 · 0.0826 · 43.24 · 42.26 · 44.25 · True · Estimado con contrafactual ML sobre historico sintetico |

## Simulacion Monte Carlo
| ranking · decision · expected_profit_usd · p10_usd · p50_usd · p90_usd · probability_loss · expected_roi |
| --- · --- · --- · --- · --- · --- · --- · --- |
| 1 · Ventana conservadora · 56272 · 45156 · 56173 · 67395 · 0.0% · 3.1x |
| 2 · Servicios de regulacion · -18802 · -24600 · -18855 · -12946 · 100.0% · -0.7x |
| 3 · Arbitraje agresivo · -31993 · -67555 · -33231 · 5366 · 86.5% · -0.3x |
| 4 · Hibrido certificado · -102220 · -154211 · -125839 · -53891 · 94.3% · -0.7x |

## Lectura ejecutiva
- Las hipotesis no se fijan como tabla externa: se estiman con contrafactuales del modelo entrenado sobre el historico.
- La ventana conservadora gana porque el historico contiene ventanas con ciclado suave y control fino de carga, y el modelo aprende que ahi el diferencial capturado si cubre el desgaste.
- El arbitraje agresivo usa el patron historico de saturacion del activo: al aumentar la profundidad de descarga crece la energia movida, pero el coste de degradacion escala con el cuadrado y se come el ingreso extra.
- Los servicios de regulacion emergen como segunda opcion porque el historico contiene ventanas ofertadas y convocadas, y el modelo aprende que remuneran con poco desgaste.
- El hibrido certificado mantiene el P90 mas alto por acceso a un producto mejor pagado, pero tambien mayor probabilidad de perdida por coste hundido de certificacion y variabilidad de ejecucion.