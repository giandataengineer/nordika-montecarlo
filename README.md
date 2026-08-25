# Vantara · Presupuesto bajo atribución rota

Sistema de Decision Intelligence para inversión de captación. Aprende del
histórico comercial, estima qué aporta cada palanca de crecimiento y simula
10.000 futuros antes de comprometer el presupuesto del trimestre.

**Consola en vivo** · https://vantara-console.vercel.app

> **Caso sintético.** Los datos se generan con distribuciones coherentes con el
> dominio de marketing de performance. No proceden de ninguna cuenta
> publicitaria real, y Vantara es una empresa ficticia.

---

## El problema

Abre el panel de Meta y te dirá que generó 400 ventas. El de Google dirá 350.
El de TikTok, 200. Suma: 950. Mira tu ecommerce: vendiste 600.

Cada plataforma se atribuye la misma venta. Tras iOS ATT la confianza en la
atribución entre canales cayó por debajo del 50 %, y el 71 % de las marcas ya
reduce su dependencia de esos datos. Con los paneles inflados, el presupuesto
se asigna a lo que mejor se reporta, no a lo que más deja.

Y el coste de captar no es lineal. El propio histórico lo dice:

| Tramo de inversión | Coste por oportunidad | Conversión | Margen por oportunidad |
|---|---|---|---|
| Bajo | $9,66 | 6,4 % | holgado |
| Alto | $14,35 | 4,9 % | estrecho |
| Saturado | $20,56 | 2,8 % | **$1** |

Doblar la inversión no dobla las ventas: satura la audiencia, sube el coste y
adelgaza el margen hasta que desaparece. Ese punto no se ve en el panel del
canal, que sigue reportando conversiones.

En la práctica esta decisión se toma con tres escenarios en una hoja de cálculo
puestos a ojo: malo menos 30 %, bueno más 30 %. Nadie sabe decir por qué 30 y no
55, ni qué probabilidad tiene, ni cuántas veces de cada cien se pierde dinero.

## El resultado

| # | Palanca | Esperado | P10 | P90 | Prob. pérdida | ROI |
|---|---|---|---|---|---|---|
| 1 | Optimizar la conversión del sitio | **+$54.119** | +$46.023 | +$62.588 | **0,00 %** | 45,1x |
| 2 | Reactivación y remarketing | +$18.347 | +$10.354 | +$26.528 | 0,03 % | 7,3x |
| 3 | Escalar paid social | +$17.299 | -$6.098 | +$40.998 | 16,99 % | 1,9x |
| 4 | Abrir categoría nueva | +$4.583 | -$29.826 | +$33.966 | 56,88 % | 0,4x |

Gana optimizar el sitio, y **gana por tener suelo positivo, no por tener la
media más alta**. Escalar paid social es lo que pide el equipo y lo que mejor
se ve en los paneles: cuesta 7 veces más de ejecutar, rinde 3 veces menos y
pierde dinero 17 de cada 100 veces.

## Arquitectura

Tres capas encadenadas. Cada una responde a una limitación concreta del
histórico; si se quita la limitación, sobra la capa.

### Capa 1 · Uplift contrafactual

El histórico registra lo que pasó, no lo que habría pasado. No existe una fila
que diga cuánto se habría facturado con la landing B en vez de la A.

- `LogisticRegression` estima si la oportunidad convertirá
- `HistGradientBoostingRegressor` estima el ticket esperado
- `Pipeline` con `ColumnTransformer` + `OneHotEncoder` + `StandardScaler`
- **Corte temporal, no aleatorio**: el 25 % final del periodo se reserva entero.
  Un `train_test_split` aleatorio sobre datos fechados filtra el futuro al
  entrenamiento y devuelve una métrica que no existe en producción.
- AUC de validación: **0,745**

El contrafactual arrastra las consecuencias mecánicas de la palanca, no solo su
valor categórico: al escalar paid social también sube el coste por oportunidad
al tramo saturado. Sin eso, la palanca central del caso medía uplift cero.

### Capa 2 · Simulación Monte Carlo

Un número esconde el riesgo; una distribución lo enseña. 10.000 escenarios por
palanca con tres ruidos calibrados por separado:

| Ruido | Distribución | Qué modela |
|---|---|---|
| Incertidumbre | Lognormal | Volatilidad de demanda y de CPM, con la cola derecha gruesa que tiene un lanzamiento |
| Ejecución | Discreta | Que la palanca se aplique completa, a medias o se caiga del roadmap |
| Residual | Gaussiana | Error del modelo |

Análisis de robustez incluido: intervalos bootstrap del uplift, estabilidad del
ranking con 30 semillas, sensibilidad escalando cada ruido a 0,5x / 1x / 1,5x /
2x, y EVPI (valor esperado de la información perfecta).

### Capa 3 · Tres lecturas independientes

Los mismos números leídos desde Finanzas, Growth y Riesgo. Cada rol corre en
**un modelo y un proveedor distintos**, con anticolisión: si otro rol ya usó un
modelo, ese modelo baja al final de la cola. Tres prompts al mismo modelo no son
tres opiniones.

- **57 combinaciones modelo+proveedor** verificadas contra las APIs reales
- 6 proveedores: Groq, Gemini, OpenRouter, Mistral, NVIDIA NIM, Z.ai
- Enfriamiento de 90 s tras un 429, y cadena de reemplazo completa
- Probado apagando los tres proveedores principales a la vez: los tres roles
  siguen respondiendo en modelos distintos
- **Sin claves el sistema funciona igual**, cayendo al camino determinista

**Guardarraíl de coherencia**: seis reglas revisan cada frase generada contra
las cifras que la acompañan. Una frase que diga «suelo positivo» cuando el P10
es negativo se retira y queda registrada como incidencia.

---

## Puesta en marcha

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. genera datos, entrena, simula y escribe los CSV
python scripts/simulacion_montecarlo.py

# 2. congela el resultado para el navegador (motor.json + payload.json)
python scripts/exportar_web.py

# 3. la consola React
cd web && npm install && npm run dev         # localhost:5173
```

La consola desplegada no necesita servidor: el remuestreo bootstrap y los tres
ruidos son aritmética y corren en el navegador sobre `motor.json`. Para el modo
con backend y fases orquestadas:

```bash
python scripts/mission_control_server.py     # 127.0.0.1:8765
```

Las claves de LLM son opcionales. Para activarlas:

```bash
cp .env.example .env    # y rellena las que tengas
```

## Estructura

```
scripts/
  simulacion_montecarlo.py    generador, modelos, escenarios, Monte Carlo, checks
  analitica_avanzada.py       guardarrail, bootstrap, estabilidad, sensibilidad, EVPI
  agente_multirol.py          los tres roles, catálogo de 57 modelos, cadena de fallback
  agente_montecarlo.py        herramientas del agente y memo ejecutiva
  dashboard_agente_demo.py    construcción del payload y consola HTML
  exportar_web.py             congela motor y payload para la web sin backend
  mission_control_server.py   API y orquestación de fases
web/                          consola React (Vite, Recharts, Motion)
datos/                        CSV generados por el pipeline
```

## Esquema de datos

Cada fila es una **oportunidad comercial**: 20.000 registros entre enero de 2024
y abril de 2026, $2,19M de ingreso y un 7,8 % de inversión sobre ingreso.

| Grupo | Columnas |
|---|---|
| Contexto comercial | `channel`, `campaign_objective`, `customer_segment`, `lifecycle_stage`, `device`, `geo_region` |
| Inversión | `ad_budget_level`, `campaign_daily_spend_usd`, `cost_attributed_usd` |
| Palancas de funnel | `landing_variant`, `cta_variant`, `lead_magnet`, `checkout_simplified` |
| Señales de intención | `lead_score`, `webinar_invited`, `webinar_attended`, `new_product_offer` |
| Resultado | `converted_to_sale`, `days_to_close`, `aov_usd`, `revenue_usd`, `gross_profit_usd`, `contribution_profit_usd` |

Objetivo del modelo de clasificación: `converted_to_sale`.

## Verificación

```bash
python scripts/simulacion_montecarlo.py    # PASS en 3 checks de calidad
python scripts/analitica_avanzada.py       # autocomprobaciones
python scripts/agente_multirol.py          # autocomprobaciones
python -m pytest tests/ -q                 # 12 tests
```

Los tres checks del pipeline validan el dataset, que los parámetros emerjan del
histórico (incluido que el tramo saturado convierta menos que el medio) y que la
conclusión se sostenga: la ganadora tiene P10 positivo, abrir categoría nueva es
la más dispersa y escalar paid social pierde dinero más de un 5 % de las veces.

## Stack

**Datos y ML** · Python · pandas · NumPy · scikit-learn
**Simulación** · Monte Carlo · lognormal, discreta y gaussiana · bootstrap · EVPI
**LLM** · SDK de OpenAI como protocolo · 6 proveedores · 57 modelos
**Backend** · `http.server` (biblioteca estándar), opcional
**Frontend** · React 19 · Vite 6 · Recharts · Motion · OGL

Sin Spark ni orquestadores distribuidos a propósito: son 20.000 filas y caben en
memoria. Añadirlos sería complejidad sin justificación.
