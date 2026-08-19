# Fluenta · Despacho bajo incertidumbre

Sistema de Decision Intelligence para operación de baterías de red. Aprende del
histórico de despacho, estima qué aporta cada palanca de operación y simula
10.000 futuros antes de comprometer la estrategia del año.

> **Caso sintético.** Los datos se generan con distribuciones coherentes con el
> dominio eléctrico. No proceden de ningún operador de red real, y Fluenta es
> una empresa ficticia.

---

## El problema

Una batería de 20 MW / 80 MWh conectada a la red. Cuatro formas de operarla
durante un año y solo se puede elegir una: no hay ensayo general.

La batería gana dinero cargando cuando el precio marginal está bajo y
descargando cuando está alto. Pero **cada ciclo desgasta las celdas, y el
desgaste crece con el cuadrado de la profundidad de descarga**: bajar el doble
de profundo no cuesta el doble, cuesta unas cuatro veces más.

Ese coste no aparece en la liquidación del día. Aparece años después, como un
activo que ya no entrega los 80 MWh que prometía. Por eso la estrategia que más
factura puede ser la que destruye el activo.

En la práctica esta decisión se toma con tres escenarios en una hoja de cálculo
puestos a ojo: malo menos 30 %, bueno más 30 %. Nadie sabe decir por qué 30 y no
55, ni qué probabilidad tiene, ni cuántas veces de cada cien se pierde dinero.

## El resultado

| # | Estrategia | Esperado | P10 | P90 | Prob. pérdida | ROI |
|---|---|---|---|---|---|---|
| 1 | Ventana conservadora | **+$56.272** | +$45.156 | +$67.395 | **0,00 %** | 3,13x |
| 2 | Servicios de regulación | -$18.802 | -$24.600 | -$12.946 | 99,99 % | - |
| 3 | Arbitraje agresivo | -$31.993 | -$67.555 | +$5.366 | 86,53 % | - |
| 4 | Híbrido certificado | -$102.220 | -$154.211 | -$53.891 | 94,29 % | - |

Gana la estrategia conservadora, y **gana por tener suelo positivo, no por tener
la media más alta**. Elegir la intuitiva (arbitraje agresivo) cuesta $88.265 en
un año sobre la misma batería.

## Arquitectura

Tres capas encadenadas. Cada una responde a una limitación concreta del
histórico; si se quita la limitación, sobra la capa.

### Capa 1 · Uplift contrafactual

El histórico registra lo que pasó, no lo que habría pasado. No existe una fila
que diga cuánto se habría ganado descargando al 80 % en vez de al 50 %.

- `LogisticRegression` estima si el ciclo cubrirá su coste de degradación
- `HistGradientBoostingRegressor` estima el ingreso esperado del ciclo
- `Pipeline` con `ColumnTransformer` + `OneHotEncoder` + `StandardScaler`
- **Corte temporal, no aleatorio**: el 25 % final del periodo se reserva entero.
  Un `train_test_split` aleatorio sobre datos fechados filtra precios del futuro
  al entrenamiento y devuelve una métrica que no existe en producción.
- AUC de validación: **0,721**

El contrafactual arrastra las consecuencias mecánicas de la palanca, no solo su
valor categórico: al cambiar a descarga profunda también escala el coste de
degradación (factor 2,1x). Sin eso, la palanca central del caso medía uplift
cero.

### Capa 2 · Simulación Monte Carlo

Un número esconde el riesgo; una distribución lo enseña. 10.000 escenarios por
estrategia con tres ruidos calibrados por separado:

| Ruido | Distribución | Qué modela |
|---|---|---|
| Incertidumbre | Lognormal | Volatilidad del precio spot, con la cola derecha gruesa que tienen los mercados eléctricos |
| Ejecución | Discreta | Ofertar y no ser convocado, recorte de inyección |
| Residual | Gaussiana | Error del modelo |

Análisis de robustez incluido: intervalos bootstrap del uplift, estabilidad del
ranking con 30 semillas, sensibilidad escalando cada ruido a 0,5x / 1x / 1,5x /
2x, y EVPI (valor esperado de la información perfecta).

### Capa 3 · Tres lecturas independientes

Los mismos números leídos desde Finanzas, Operación del activo y Riesgo. Cada
rol corre en **un modelo y un proveedor distintos**, con anticolisión: si otro
rol ya usó un modelo, ese modelo baja al final de la cola. Tres prompts al mismo
modelo no son tres opiniones.

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

# 2. levanta la API (http.server, sin framework)
python scripts/mission_control_server.py     # 127.0.0.1:8765

# 3. la consola React, en otra terminal
cd web && npm install && npm run dev         # localhost:5173
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
  mission_control_server.py   API y orquestación de fases
web/                          consola React (Vite, Recharts, Motion)
datos/                        CSV generados por el pipeline
```

## Esquema de datos

Cada fila es una **ventana de despacho de una hora**.

| Grupo | Columnas |
|---|---|
| Control de operación | `profundidad_descarga`, `ventana_carga`, `rampa_optimizada`, `reserva_comprometida` |
| Condiciones de mercado | `precio_spot_usd_mwh`, `diferencial_usd_mwh`, `estado_red`, `bloque_horario` |
| Estado del activo | `soc_inicial_pct`, `ciclos_acumulados`, `coste_degradacion_usd`, `indice_despacho` |
| Productos de mercado | `regulacion_ofertada`, `regulacion_convocada`, `mercado_nuevo`, `zona_red` |
| Resultado | `cubrio_degradacion`, `ingreso_usd`, `margen_bruto_usd`, `margen_neto_usd` |

Objetivo del modelo de clasificación: `cubrio_degradacion`, es decir, si el
ciclo llegó a cubrir su propio coste de desgaste.

## Verificación

```bash
python scripts/simulacion_montecarlo.py    # PASS en 3 checks de calidad
python scripts/analitica_avanzada.py       # autocomprobaciones
python scripts/agente_multirol.py          # autocomprobaciones
```

Los tres checks del pipeline validan el dataset, que los parámetros emerjan del
histórico (incluido que la descarga profunda destruya margen) y que la
conclusión se sostenga: la ganadora tiene P10 positivo y la agresiva es la más
dispersa.

## Stack

**Datos y ML** · Python · pandas · NumPy · scikit-learn
**Simulación** · Monte Carlo · lognormal, discreta y gaussiana · bootstrap · EVPI
**LLM** · SDK de OpenAI como protocolo · 6 proveedores · 57 modelos
**Backend** · `http.server` (biblioteca estándar)
**Frontend** · React 19 · Vite 6 · Recharts · Motion · OGL

Sin Spark ni orquestadores distribuidos a propósito: son 20.000 filas y caben en
memoria. Añadirlos sería complejidad sin justificación.
