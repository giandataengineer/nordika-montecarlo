-- Serie mensual con media movil de tres meses. La funcion de ventana es la
-- razon por la que esto vive en SQL y no en pandas.
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
