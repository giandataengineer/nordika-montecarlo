import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Bullets, Metric, MetricGrid, Panel } from "./Blocks";
import { pct, usd, usdK } from "../lib/format";
import { IconAlert, IconCheck, IconLayers } from "./Icons";

/* Las tres preguntas que separan un simulador de una herramienta de decision:
   ¿aguanta el ranking?, ¿aguanta si me equivoque calibrando?, ¿cuanto vale
   quitarme la incertidumbre antes de decidir? */
export function RobustezSection({ payload }) {
  const a = payload?.avanzado;
  if (!a) return <Panel>Calculando robustez...</Panel>;

  const est = a.estabilidad ?? {};
  const sens = a.sensibilidad ?? {};
  const evpi = a.valor_informacion ?? {};
  const val = a.validacion ?? {};

  const barras = (est.detalle ?? []).map((d) => ({
    name: d.decision,
    tasa: d.tasa_victoria * 100,
    victorias: d.victorias,
    total: d.realizaciones,
  }));

  const reparto = (evpi.reparto_de_escenarios ?? []).map((r) => ({
    name: r.decision,
    cuota: r.cuota_escenarios * 100,
  }));

  return (
    <div className="stack">
      <MetricGrid cols={4}>
        <Metric
          label="Ganador estable"
          value={est.ganador_estable ? "Sí" : "No"}
          gloss={est.veredicto}
          accent={est.ganador_estable}
        />
        <Metric
          label="Robusto al ruido"
          value={sens.robusto ? "Sí" : "Parcial"}
          gloss={sens.veredicto}
        />
        <Metric
          label="Valor de la información"
          value={usd(evpi.evpi)}
          gloss="Techo de lo que compensa gastar en reducir incertidumbre"
          accent
        />
        <Metric
          label="Acierto de la apuesta"
          value={pct(evpi.acierto_de_la_apuesta)}
          gloss="Escenarios en los que la opción elegida es realmente la mejor"
        />
      </MetricGrid>

      <div className="split-2">
        <Panel eyebrow="Estabilidad" title={`Victorias en ${est.realizaciones ?? 0} realizaciones`}>
          <p className="panel__copy">
            Un ranking presentado como definitivo esconde cuánto depende de la realización
            concreta que tocó. Aquí se repite la simulación con {est.realizaciones ?? 0} semillas
            distintas y se cuenta quién gana cada vez.
          </p>
          <div className="chart">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barras} layout="vertical" margin={{ left: 4, right: 20 }}>
                <CartesianGrid stroke="var(--line)" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="name" width={150} stroke="var(--faint)" tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v, k, p) => [`${v.toFixed(0)}% (${p.payload.victorias}/${p.payload.total})`, "Victorias"]}
                  contentStyle={{ background: "var(--panel-warm)", border: "1px solid var(--line)", borderRadius: 10 }}
                />
                <Bar dataKey="tasa" radius={[0, 4, 4, 0]} animationDuration={1200}>
                  {barras.map((d) => (
                    <Cell key={d.name} fill={d.tasa >= 80 ? "var(--green)" : "var(--ghost)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <span className="card__foot label">{est.alcance}</span>
        </Panel>

        <Panel eyebrow="Sensibilidad" title="Qué pasa si el ruido está mal calibrado">
          <p className="panel__copy">
            La magnitud de los tres ruidos la elige el analista, así que hay que ver
            cuánto depende la recomendación de esa elección. Aquí se escala cada uno por
            separado para saber a partir de qué exageración cambiaría la decisión.
          </p>
          <div className="sens-grid">
            {(sens.resultados ?? []).map((r) => (
              <article className={`sens ${r.punto_de_quiebre ? "sens--frag" : ""}`} key={r.ruido}>
                <div className="sens__head">
                  <span className="label">{r.ruido}</span>
                  {r.punto_de_quiebre ? (
                    <span className="sens__flag sens__flag--warn">
                      <IconAlert style={{ width: 13, height: 13 }} />
                      cambia en ×{r.punto_de_quiebre}
                    </span>
                  ) : (
                    <span className="sens__flag sens__flag--ok">
                      <IconCheck style={{ width: 13, height: 13 }} />
                      aguanta hasta ×2
                    </span>
                  )}
                </div>
                <div className="sens__track">
                  {(r.puntos ?? []).map((p) => (
                    <div className={`sens__pt ${p.cambia ? "is-break" : ""}`} key={p.factor}>
                      <span className="sens__factor">×{p.factor}</span>
                      <span className="sens__winner">{p.ganador}</span>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </Panel>
      </div>

      <div className="split-2">
        <Panel eyebrow="Valor de la información" title="Cuánto vale saber el futuro de antemano">
          <p className="panel__copy">
            Bajo incertidumbre eliges la de mayor media y te quedas con ella pase lo que
            pase. Con información perfecta elegirías, en cada escenario, la que mejor
            sale ahí. La diferencia entre las dos es el techo de lo que tiene sentido
            gastar en un piloto o en mejores datos.
          </p>
          <MetricGrid cols={2}>
            <Metric label="Sin información" value={usd(evpi.valor_sin_informacion)} gloss={evpi.decision_sin_informacion} />
            <Metric label="Con información perfecta" value={usd(evpi.valor_con_informacion_perfecta)} gloss="Eligiendo lo mejor en cada escenario" />
          </MetricGrid>
          <div className="chart">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={reparto} layout="vertical" margin={{ left: 4, right: 20 }}>
                <CartesianGrid stroke="var(--line)" horizontal={false} />
                <XAxis type="number" stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                <YAxis type="category" dataKey="name" width={150} stroke="var(--faint)" tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(v) => [`${v.toFixed(1)}% de los escenarios`, "Es la mejor en"]}
                  contentStyle={{ background: "var(--panel-warm)", border: "1px solid var(--line)", borderRadius: 10 }}
                />
                <Bar dataKey="cuota" radius={[0, 4, 4, 0]} fill="var(--purple)" animationDuration={1200} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <span className="card__foot label">{evpi.lectura}</span>
        </Panel>

        <Panel eyebrow="Validación" title="Cómo se comprobó que los modelos generalizan">
          <p className="panel__copy">
            Una partición aleatoria sobre datos con fecha entrena con registros
            posteriores a los de validación. El modelo aprende con información del
            futuro y la métrica sale inflada. Aquí el corte es temporal, que es como se
            va a usar en producción.
          </p>
          <MetricGrid cols={2}>
            <Metric label="Entrenamiento" value={`${val.train_start} → ${val.train_end}`} gloss={`${Number(val.train_rows || 0).toLocaleString("en-US")} registros, la parte antigua`} />
            <Metric label="Validación" value={`${val.test_start} → ${val.test_end}`} gloss={`${Number(val.test_rows || 0).toLocaleString("en-US")} registros, nunca vistos al entrenar`} accent />
          </MetricGrid>
          <Bullets
            icon={IconLayers}
            tone="var(--blue)"
            items={[
              "El corte sale de una única función compartida. Las métricas del panel y las del pipeline no se pueden desincronizar.",
              "El uplift de cada palanca lleva intervalo de confianza calculado por bootstrap, lo que permite comprobar si el efecto llega a cruzar el cero.",
              "La semilla está fija. Si dos ejecuciones no coinciden, es que cambió el código o cambiaron los datos, no el azar.",
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}
