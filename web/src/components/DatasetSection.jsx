import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import DecryptedText from "../reactbits/DecryptedText";
import { Metric, MetricGrid, Panel } from "./Blocks";
import { num, pct, usd, usdK } from "../lib/format";

export function DatasetSection({ payload }) {
  const s = payload?.dataset?.summary;
  const monthly = payload?.dataset?.monthly ?? [];
  const sample = payload?.dataset?.sample ?? [];

  if (!s) return <Panel>Cargando base histórica...</Panel>;

  const serie = monthly.map((m) => ({
    month: m.month,
    revenue: Number(m.ingreso_usd || 0),
    profit: Number(m.margen_neto_usd || 0),
    conv: Number(m.conversion_rate || 0) * 100,
  }));

  return (
    <div className="stack">
      <MetricGrid cols={4}>
        <Metric
          label="Periodo cubierto"
          value={`${s.period_start} → ${s.period_end}`}
          gloss="Ventana histórica utilizada en el análisis"
        />
        <Metric
          label="Conversión observada"
          value={pct(s.conversion_rate)}
          gloss="Ventanas que cubrieron su coste de degradación"
        />
        <Metric
          label="Energía por ciclo"
          value={`${Number(s.avg_ticket_usd || 0).toFixed(1)} MWh`}
          gloss="Energía media movida en las ventanas que cubrieron su degradación"
        />
        <Metric
          label="Beneficio acumulado"
          value={usd(s.margen_neto_usd)}
          gloss="Beneficio de contribución total del histórico"
          accent
        />
      </MetricGrid>

      <div className="split-2">
        <Panel eyebrow="Cobertura del caso" title="Qué información tiene disponible el agente">
          <p className="panel__copy">
            Antes de modelizar conviene comprobar que el caso tiene suficiente diversidad
            de operación: bloques horarios, productos, nodos, estados de red y ventana temporal.
          </p>
          <MetricGrid cols={4}>
            <Metric label="Regímenes" value={s.campaign_count} animate gloss="Combinaciones distintas de bloque horario y producto de mercado" />
            <Metric label="Variables" value={s.variable_count} animate gloss="Campos disponibles para explicar comportamiento y resultado" />
            <Metric label="Productos" value={s.segment_count} animate gloss="Productos de mercado a los que puede acudir la batería" />
            <Metric label="Geografías" value={s.geography_count} animate gloss="Mercados presentes en la base histórica" />
          </MetricGrid>
          <MetricGrid cols={3}>
            <Metric label="Bloques horarios" value={s.channel_count} animate gloss="Franjas de la curva de demanda diaria" />
            <Metric label="Estados de red" value={s.objective_count} animate gloss="Nivel de tensión del sistema marcado por el operador" />
            <Metric label="Índice de despacho" value={s.avg_lead_score.toFixed(1)} gloss="Atractivo medio de la ventana, de 1 a 99" />
          </MetricGrid>
        </Panel>

        <Panel eyebrow="Serie temporal" title="Evolución mensual del negocio">
          <p className="panel__copy">
            La serie de revenue y beneficio de contribución da contexto sobre la estabilidad
            del negocio antes de evaluar nuevas palancas.
          </p>
          <div className="chart chart--tall">
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={serie} margin={{ left: 0, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="gRev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--blue)" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="var(--blue)" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gPro" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--green)" stopOpacity={0.24} />
                    <stop offset="100%" stopColor="var(--green)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="month" stroke="var(--faint)" tick={{ fontSize: 12 }} interval={6} />
                <YAxis stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={usdK} width={58} />
                <Tooltip
                  formatter={(v, k) => [usd(v), k === "revenue" ? "Revenue" : "Beneficio"]}
                  contentStyle={{ background: "var(--panel-warm)", border: "1px solid var(--line)", borderRadius: 10 }}
                />
                <Legend
                  formatter={(v) => (v === "revenue" ? "Revenue" : "Beneficio de contribución")}
                  wrapperStyle={{ fontSize: 12, fontFamily: "var(--font-mono)" }}
                />
                <Area type="monotone" dataKey="revenue" stroke="var(--blue)" strokeWidth={1.8} fill="url(#gRev)" animationDuration={1400} />
                <Area type="monotone" dataKey="profit" stroke="var(--green)" strokeWidth={1.8} strokeDasharray="4 3" fill="url(#gPro)" animationDuration={1700} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel eyebrow="Muestra del dataset" title={`Primeras ${sample.length} filas de ${num(s.rows)} registros`}>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Bloque</th>
                <th>Segmento</th>
                <th>Objetivo</th>
                <th className="ta-r">Índice</th>
                <th className="ta-r">Conversión</th>
                <th className="ta-r">Revenue</th>
                <th className="ta-r">Beneficio</th>
              </tr>
            </thead>
            <tbody>
              {sample.map((r, i) => (
                <tr key={i}>
                  <td>{r.date}</td>
                  <td>{r.channel}</td>
                  <td>{r.customer_segment}</td>
                  <td>{r.campaign_objective}</td>
                  <td className="ta-r">{r.indice_despacho}</td>
                  <td className="ta-r">
                    <span className={r.cubrio_degradacion ? "flag flag--yes" : "flag"}>
                      {r.cubrio_degradacion ? "Sí" : "No"}
                    </span>
                  </td>
                  <td className="ta-r">{usd(r.ingreso_usd)}</td>
                  <td className={`ta-r ${Number(r.margen_neto_usd) < 0 ? "neg" : ""}`}>
                    {usd(r.margen_neto_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <span className="card__foot label">
          <DecryptedText
            text={`${num(s.rows)} registros · ${s.time_windows} ventanas temporales · ${num(s.ingreso_usd)} de revenue histórico`}
            animateOn="view"
            speed={20}
            sequential
            revealDirection="start"
          />
        </span>
      </Panel>
    </div>
  );
}
