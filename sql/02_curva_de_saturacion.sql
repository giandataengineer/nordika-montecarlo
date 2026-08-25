-- El hallazgo central: al subir el nivel de inversión crece el volumen,
-- cae la calidad del lead y el margen por oportunidad se da la vuelta.
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
