# Evaluación del dataset transaccional sintético

## Checks
- dataset_transaccional_20k: PASS
- parametros_emergen_del_historico: PASS
- conclusion_y_narrativa: PASS

## Baseline histórico
- Registros: 20,000
- Periodo: 2024-01-01 a 2026-04-30
- Conversión media: 9.9%
- Revenue histórico: 2,186,421 USD
- Contribution profit histórico: 1,409,206 USD
- AUC modelo de conversión: 0.745

## Variables clave para estimar hipotesis
- Cambios de funnel: landing_variant, cta_variant, lead_magnet, checkout_simplified.
- Presion de ads: ad_budget_level, campaign_daily_spend_usd, cost_attributed_usd, lead_score.
- Webinar: webinar_invited, webinar_attended.
- Abrir categoría nueva: new_product_offer, customer_segment, aov_usd, gross_margin_pct.
- Resultado de negocio: converted_to_sale, revenue_usd, gross_profit_usd, contribution_profit_usd.

## Resumen por canal
| channel | registros | conversion | revenue_usd | contribution_profit_usd | coste_medio |
| --- | --- | --- | --- | --- | --- |
| Afiliados | 1732 | 7.8% | 145309 | 84834 | 7.14 |
| Email | 3248 | 19.2% | 693853 | 515377 | 0.72 |
| Facebook Ads | 4648 | 4.6% | 217580 | 75677 | 15.99 |
| Google Ads | 3254 | 6.1% | 217881 | 109713 | 13.25 |
| SEO / Blog | 3106 | 11.9% | 417111 | 298201 | 1.84 |
| TikTok Ads | 2362 | 5.8% | 140181 | 72462 | 10.36 |
| Webinar | 1650 | 17.9% | 354506 | 252942 | 5.65 |

## Parámetros estimados desde histórico
| parameter | sample_size | baseline_conversion | scenario_conversion | conversion_lift_pct | profit_lift_per_opportunity_usd | profit_lift_ci_low_usd | profit_lift_ci_high_usd | profit_lift_significativo | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| funnel_full_optimized | 20000 | 0.0959 | 0.1334 | 0.3917 | 29.55 | 29.17 | 30.01 | True | Estimado con contrafactual ML sobre histórico sintético |
| paid_budget_low | 792 | 0.0682 | 0.0642 |  | 35.46 | nan | nan | nan | Histórico por nivel de inversión en ads |
| paid_budget_medium | 3320 | 0.0645 | 0.0645 |  | 34.42 | nan | nan | nan | Histórico por nivel de inversión en ads |
| paid_budget_high | 2030 | 0.0498 | 0.0448 |  | 18.27 | nan | nan | nan | Histórico por nivel de inversión en ads |
| paid_budget_saturated | 1760 | 0.025 | 0.027 |  | -1.07 | nan | nan | nan | Histórico por nivel de inversión en ads |
| webinar_attendance | 13561 | 0.1239 | 0.1742 | 0.4061 | 48.11 | 47.57 | 48.69 | True | Estimado con contrafactual ML sobre histórico sintético |
| new_product_offer | 11607 | 0.1061 | 0.0609 | -0.426 | 15.39 | 14.79 | 16.01 | True | Estimado con contrafactual ML sobre histórico sintético |

## Simulación Monte Carlo
| ranking | decision | expected_profit_usd | p10_usd | p50_usd | p90_usd | probability_loss | expected_roi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Optimizar la conversión del sitio | 54119 | 46023 | 53965 | 62588 | 0.0% | 45.1x |
| 2 | Reactivación y remarketing | 18347 | 10354 | 18170 | 26528 | 0.0% | 7.3x |
| 3 | Escalar paid social | 17299 | -6098 | 17010 | 40998 | 17.0% | 1.9x |
| 4 | Abrir categoría nueva | 4583 | -29826 | -3798 | 33966 | 56.9% | 0.4x |

## Lectura ejecutiva
- Las hipotesis no se fijan como tabla externa: se estiman con contrafactuales del modelo entrenado sobre el histórico.
- Mejorar el funnel gana porque el histórico contiene tests de landing, CTA, lead magnet y checkout que el modelo aprende como mejora de conversión.
- Duplicar ads usa el patron histórico de saturación: cuando sube el nivel de inversión, crece el volumen pero baja la calidad media y sube el coste por oportunidad.
- Webinar emerge como buena segunda opción porque el histórico contiene invitados/asistentes y el modelo aprende uplift en leads templados.
- Abrir categoría nueva mantiene el P90 más alto por ticket mayor, pero también mayor probabilidad de pérdida por menor conversión, coste fijo y variabilidad de ejecución.