-- Cuantas oportunidades pagan de verdad el ano: acumulado por percentil.
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
