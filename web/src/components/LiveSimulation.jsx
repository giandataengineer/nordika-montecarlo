import { useMemo } from "react";
import {
  CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import CountUp from "../reactbits/CountUp";
import Magnet from "../reactbits/Magnet";
import { Metric, MetricGrid, Panel } from "./Blocks";
import { pct, roi, usd, usdK } from "../lib/format";
import { IconAlert, IconSimulate } from "./Icons";

const HEX = ["#158a5c", "#2f80ed", "#d9531e", "#7c3aed"];
const HEX_TEXT = ["#117a50", "#1c62c4", "#b8420f", "#6a2bd6"];
const TONES = ["var(--green)", "var(--blue)", "var(--orange)", "var(--purple)"];

/* Tooltip propio: el de recharts por defecto no dice de qué decisión habla
   cuando hay cuatro series encima. */
function Caja({ active, payload, label, sufijo }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tt">
      {label != null && <span className="tt__label">{sufijo ? `${label} ${sufijo}` : label}</span>}
      {payload.map((p) => (
        <span className="tt__fila" key={p.dataKey ?? p.name}>
          <i style={{ background: p.color ?? p.fill }} />
          <b>{p.name ?? p.dataKey}</b>
          <em>{usd(p.value)}</em>
        </span>
      ))}
    </div>
  );
}

/* Cada alternativa es un contacto en un radar: el punto solido con su anillo
   de barrido girando y un pulso que se expande. Mientras corre la simulación
   el barrido va mas rapido, porque hay mas contactos entrando. */
/* Cada alternativa lleva su propio radar: el barrido gira sobre el punto y
   deja un eco que se expande. Se dibuja desde el origen dentro de un <g>
   trasladado, porque un transform-origin en píxeles sobre un <g> de SVG no
   aplica de forma fiable entre navegadores. */
function PuntoRadar({ cx, cy, fill, corriendo, idx = 0 }) {
  if (cx == null || cy == null) return null;
  const ciclo = corriendo ? "2.2s" : "3.6s";
  const giro = corriendo ? "2.6s" : "5s";
  const R = 26;
  const apertura = 60;
  const rad = (apertura * Math.PI) / 180;
  const id = `haz-${idx}`;

  return (
    <g className="radar-pt" transform={`translate(${cx} ${cy})`}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={fill} stopOpacity="0.55" />
          <stop offset="100%" stopColor={fill} stopOpacity="0" />
        </linearGradient>
      </defs>

      <circle r={R} fill={fill} fillOpacity="0.07" />
      <circle r={R} fill="none" stroke={fill} strokeOpacity="0.22" strokeWidth="1" />
      <circle r={R * 0.55} fill="none" stroke={fill} strokeOpacity="0.16" strokeWidth="1" />

      <g className="radar-pt__barrido" style={{ animationDuration: giro }}>
        <path
          d={`M 0 0 L ${R} 0 A ${R} ${R} 0 0 1 ${R * Math.cos(rad)} ${R * Math.sin(rad)} Z`}
          fill={`url(#${id})`}
        />
        <line x1="0" y1="0" x2={R} y2="0" stroke={fill} strokeOpacity="0.6" strokeWidth="1" />
      </g>

      <circle r="6" fill="none" stroke={fill} strokeWidth="1.5">
        <animate attributeName="r" values={`6;${R};6`} dur={ciclo} repeatCount="indefinite" />
        <animate attributeName="stroke-opacity" values="0.6;0;0.6" dur={ciclo} repeatCount="indefinite" />
      </circle>

      <circle r="6" fill={fill} />
      <circle r="2.4" fill="#fff" fillOpacity="0.6" />
    </g>
  );
}

function AnilloProgreso({ pct: p, iteracion, total, corriendo }) {
  const R = 92;
  const C = 2 * Math.PI * R;
  return (
    <div className="ring">
      <svg viewBox="0 0 220 220" className="ring__svg">
        <circle cx="110" cy="110" r={R} fill="none" stroke="var(--line)" strokeWidth="10" />
        <circle
          cx="110" cy="110" r={R} fill="none"
          stroke="var(--accent)" strokeWidth="10" strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={C * (1 - p / 100)}
          transform="rotate(-90 110 110)"
          style={{ transition: "stroke-dashoffset .35s linear" }}
        />
      </svg>
      <div className="ring__inner">
        <span className="label">Progreso</span>
        <strong className="ring__pct">{p.toFixed(1)}%</strong>
        <span className="ring__sub">
          Futuro {Number(iteracion).toLocaleString("en-US")} de {Number(total).toLocaleString("en-US")}
        </span>
        {corriendo && <span className="ring__live"><i /> simulando</span>}
      </div>
    </div>
  );
}

/* Pantalla previa: mientras no se lance la simulación no hay resultados que
   enseñar, y enseñarlos igualmente haría que el botón no significara nada. */
function Compuerta({ total, onLanzar }) {
  return (
    <Panel eyebrow="Fase 04 · Simulación Monte Carlo" title="Todavía no hay resultados que mostrar" className="compuerta">
      <p className="panel__copy">
        Los modelos ya estimaron el uplift de cada palanca, pero eso es una única
        predicción. Para saber qué decisión aguanta hace falta simular
        {" "}{Number(total).toLocaleString("en-US")} futuros inyectando incertidumbre,
        riesgo de ejecución y ruido residual. El ranking, el radar y el informe
        aparecen cuando termine.
      </p>
      <div className="compuerta__cta">
        <Magnet padding={80} magnetStrength={6}>
          <button className="pill-btn compuerta__btn" type="button" onClick={onLanzar}>
            <IconSimulate style={{ width: 16, height: 16 }} />
            Empezar la simulación de {Number(total).toLocaleString("en-US")} futuros
          </button>
        </Magnet>
        <span className="label">Los resultados aparecen al terminar · unos 30 segundos</span>
      </div>
      <ul className="compuerta__pasos">
        <li><b>1</b> Muestrea los parámetros de cada palanca de su distribución</li>
        <li><b>2</b> Sortea si la ejecución sale completa, a medias o se cae</li>
        <li><b>3</b> Añade el ruido que el modelo no explica</li>
        <li><b>4</b> Repite y ordena por esperanza ajustada a riesgo</li>
      </ul>
    </Panel>
  );
}

export function LiveSimulation({ payload, sim }) {
  const finales = payload?.simulation?.summary ?? [];
  const total = sim.total;

  // Durante el run mandan los datos parciales del backend; al terminar, el
  // resumen consolidado. Nunca se mezcla una cosa con la otra.
  const filas = sim.corriendo && sim.leaderboard.length ? sim.leaderboard : sim.lista ? finales : [];

  const orden = useMemo(() => {
    const m = new Map();
    finales.forEach((r, i) => m.set(r.decision, i));
    return m;
  }, [finales]);

  const tono = (nombre, i) => HEX[(orden.get(nombre) ?? i) % HEX.length];

  const radar = filas.map((r, i) => ({
    x: Number(r.probability_loss) * 100,
    y: Number(r.expected_profit_usd),
    z: 300,
    name: r.decision,
    tone: tono(r.decision, i),
    idx: i,
  }));

  const nombres = filas.map((r) => r.decision);

  if (sim.estado === "espera") return <Compuerta total={total} onLanzar={sim.lanzar} />;

  return (
    <div className="stack">
      <Panel eyebrow="Mission control" title={sim.corriendo ? "Simulación en directo" : "Simulación completada"}>
        <p className="panel__copy">
          Cada punto del recorrido es un futuro distinto. El progreso y las cifras vienen de
          <code> /api/montecarlo-status</code>: son escenarios realmente completados en el backend.
        </p>

        <div className="live-top">
          <MetricGrid cols={3}>
            <Metric
              label="Estado"
              value={sim.corriendo ? "En marcha" : "Completada"}
              gloss={sim.mensaje || `${Number(sim.iteracion).toLocaleString("en-US")} escenarios procesados`}
              accent={sim.corriendo}
            />
            <Metric label="Líder ahora" value={sim.lider?.decision ?? filas[0]?.decision ?? "-"} gloss="Cambia mientras se acumulan escenarios" />
            <Metric
              label="ROI del líder"
              value={filas[0]?.expected_roi ? roi(filas[0].expected_roi) : "-"}
              gloss="Retorno sobre la inversión comprometida"
            />
          </MetricGrid>

          <div className="live-ring">
            <AnilloProgreso pct={sim.progreso} iteracion={sim.iteracion} total={total} corriendo={sim.corriendo} />
            {!sim.corriendo && (
              <Magnet padding={70} magnetStrength={5}>
                <button className="pill-btn live-btn" type="button" onClick={sim.lanzar}>
                  <IconSimulate style={{ width: 15, height: 15 }} />
                  Volver a simular
                </button>
              </Magnet>
            )}
          </div>
        </div>
      </Panel>

      {filas.length > 0 && (
        <MetricGrid cols={4}>
          {filas.map((r, i) => (
            <div className="pos-card" key={r.decision} style={{ "--tone": TONES[(orden.get(r.decision) ?? i) % 4] }}>
              <span className="label">Posición {i + 1}</span>
              <strong className="pos-card__value">
                {sim.corriendo ? (
                  `${(Number(r.expected_profit_usd) / 1000).toFixed(1)}k`
                ) : (
                  <><CountUp to={Number(r.expected_profit_usd) / 1000} duration={1.6} />k</>
                )}
              </strong>
              <span className="pos-card__name">{r.decision}</span>
              <span className="pos-card__meta">
                Pérdida {pct(r.probability_loss)} · ROI {roi(r.expected_roi)}
              </span>
              <i className="pos-card__bar" />
            </div>
          ))}
        </MetricGrid>
      )}

      <div className="split-2">
        <Panel eyebrow="Radar riesgo / retorno" title="Dónde cae cada alternativa">
          <p className="panel__copy">
            Cuanto más arriba, mayor beneficio esperado. Cuanto más a la derecha, mayor
            probabilidad de pérdida. {sim.corriendo && "Los puntos se desplazan según entran escenarios."}
          </p>
          <div className="chart">
            <ResponsiveContainer width="100%" height={340}>
              <ScatterChart margin={{ left: 8, right: 26, top: 20, bottom: 22 }}>
                <CartesianGrid stroke="var(--line)" />
                <XAxis
                  type="number" dataKey="x" name="Riesgo"
                  domain={[0, (max) => Math.ceil((max + 6) / 5) * 5]}
                  tickFormatter={(v) => `${Math.round(v)}%`}
                  stroke="var(--faint)" tick={{ fontSize: 12 }}
                  label={{ value: "Probabilidad de pérdida", position: "insideBottom", offset: -12, fontSize: 12, fill: "var(--muted)" }}
                />
                <YAxis
                  type="number" dataKey="y" name="Beneficio" domain={[0, "dataMax + 8000"]}
                  stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={usdK} width={64}
                />
                <ZAxis type="number" dataKey="z" range={[300, 300]} />
                <ReferenceLine x={20} stroke="var(--orange)" strokeDasharray="4 4"
                  label={{ value: "riesgo alto", position: "top", fontSize: 11, fill: "var(--orange-text)" }} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ active, payload: pl }) => {
                    if (!active || !pl?.length) return null;
                    const d = pl[0].payload;
                    return (
                      <div className="tt">
                        <span className="tt__label">{d.name}</span>
                        <span className="tt__fila"><i style={{ background: d.tone }} /><b>Beneficio</b><em>{usd(d.y)}</em></span>
                        <span className="tt__fila"><i style={{ background: "var(--faint)" }} /><b>Pérdida</b><em>{d.x.toFixed(1)}%</em></span>
                      </div>
                    );
                  }}
                />
                <Scatter
                  data={radar}
                  isAnimationActive={false}
                  shape={(props) => (
                    <PuntoRadar
                      cx={props.cx} cy={props.cy}
                      fill={props.payload.tone}
                      corriendo={sim.corriendo}
                      idx={props.payload.idx}
                    />
                  )}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <ul className="legend-list">
            {radar.map((d, i) => (
              <li key={d.name}>
                <i style={{ background: d.tone }} /> {i + 1} · {d.name}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel eyebrow="Evolución del beneficio esperado" title="Cómo se mueve cada estrategia">
          <p className="panel__copy">
            Cada línea es una decisión y cada punto una lectura del backend según avanza la
            simulación. Las curvas que se estabilizan pronto son las que menos dependen de la
            suerte; las que siguen oscilando necesitan más escenarios.
          </p>
          <div className="chart">
            <ResponsiveContainer width="100%" height={330}>
              <LineChart data={sim.historial} margin={{ left: 0, right: 12, top: 8, bottom: 20 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis
                  dataKey="iter" stroke="var(--faint)" tick={{ fontSize: 12 }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                  label={{ value: "Escenarios simulados", position: "insideBottom", offset: -10, fontSize: 12, fill: "var(--muted)" }}
                />
                <YAxis stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={usdK} width={64} />
                <Tooltip content={<Caja sufijo="escenarios" />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                {nombres.map((n, i) => (
                  <Line
                    key={n} type="monotone" dataKey={n} name={n}
                    stroke={tono(n, i)} strokeWidth={2} dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          {sim.historial.length < 3 && (
            <span className="card__foot label">
              Las curvas se dibujan según llegan lecturas del backend
            </span>
          )}
        </Panel>
      </div>

      {sim.lista && finales.length > 0 && (
        <Panel eyebrow="Lectura consolidada" title="Ranking final de alternativas">
          <p className="panel__copy">
            El percentil 10 es el suelo: si es negativo, esa estrategia puede destruir margen
            aunque su mediana sea alta.
          </p>
          <div className="rank-rows">
            {finales.map((r, i) => (
              <article className="rank-row" key={r.decision} style={{ "--tone": TONES[i % 4] }}>
                <span className="rank-row__n">Ranking {r.ranking}</span>
                <h4 className="rank-row__name">{r.decision}</h4>
                <div className="rank-row__grid">
                  <span>Beneficio esperado<b>{usd(r.expected_profit_usd)}</b></span>
                  <span>P10 · suelo<b className={Number(r.p10_usd) < 0 ? "neg" : ""}>{usd(r.p10_usd)}</b></span>
                  <span>P50 · mediana<b>{usd(r.p50_usd)}</b></span>
                  <span>P90 · techo<b>{usd(r.p90_usd)}</b></span>
                  <span>Prob. pérdida<b className={Number(r.probability_loss) > 0.2 ? "neg" : ""}>{pct(r.probability_loss)}</b></span>
                  <span>ROI<b>{roi(r.expected_roi)}</b></span>
                </div>
                {Number(r.p10_usd) < 0 && (
                  <p className="rank-row__warn">
                    <IconAlert style={{ width: 14, height: 14 }} />
                    Su percentil 10 entra en pérdida: puede destruir margen aunque su mediana sea alta.
                  </p>
                )}
              </article>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
