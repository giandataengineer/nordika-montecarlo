-- De donde sale el margen y que canal esta comprando volumen caro.
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
