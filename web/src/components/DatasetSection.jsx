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
          gloss="Oportunidades que acabaron en venta"
        />
        <Metric
          label="Ticket medio"
          value={usd(s.avg_ticket_usd)}
          gloss="Valor medio de las operaciones cerradas"
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
            Antes de modelizar conviene comprobar que el caso reúne suficiente
            diversidad comercial. Se revisan las campañas ejecutadas, los canales de
            captación, los segmentos de cliente, los mercados cubiertos y la ventana
            temporal disponible.
          </p>
          <MetricGrid cols={4}>
            <Metric label="Campañas" value={s.campaign_count} animate gloss="Combinaciones distintas de canal y objetivo" />
            <Metric label="Variables" value={s.variable_count} animate gloss="Campos disponibles para explicar comportamiento y resultado" />
            <Metric label="Segmentos" value={s.segment_count} animate gloss="Perfiles de cliente presentes en el histórico" />
            <Metric label="Geografías" value={s.geography_count} animate gloss="Mercados presentes en la base histórica" />
          </MetricGrid>
          <MetricGrid cols={3}>
            <Metric label="Canales" value={s.channel_count} animate gloss="Vías de captación registradas" />
            <Metric label="Objetivos" value={s.objective_count} animate gloss="Tipos de objetivo de campaña" />
            <Metric label="Lead score medio" value={s.avg_lead_score.toFixed(1)} gloss="Calidad media de la oportunidad, de 1 a 99" />
          </MetricGrid>
        </Panel>

        <Panel eyebrow="Serie temporal" title="Evolución mensual del negocio">
          <p className="panel__copy">
            La serie mensual de ingreso y de beneficio de contribución sitúa el punto de
            partida: muestra si el negocio es estable o si arrastra una tendencia que
            conviene tener en cuenta antes de evaluar nuevas palancas.
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
          <p className="chart-lectura">
            Lo que conviene observar aquí no es el nivel de cada mes, sino la
            distancia entre las dos curvas. El ingreso marca el volumen que entra y
            el beneficio de contribución, lo que queda después de pagar la
            captación. Cuando ambas se separan, el negocio crece comprando volumen
            más caro, que es exactamente el efecto que la Fase 03 mide palanca a
            palanca.
          </p>
        </Panel>
      </div>

      <Panel eyebrow="Muestra del dataset" title={`Primeras ${sample.length} filas de ${num(s.rows)} registros`}>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Canal</th>
                <th>Segmento</th>
                <th>Inversión</th>
                <th className="ta-r">Coste</th>
                <th className="ta-r">Índice</th>
                <th className="ta-r">Convirtió</th>
                <th className="ta-r">Ingreso</th>
                <th className="ta-r">Margen</th>
              </tr>
            </thead>
            <tbody>
              {sample.map((r, i) => (
                <tr key={i}>
                  <td>{r.date}</td>
                  <td>{r.channel}</td>
                  <td>{r.customer_segment}</td>
                  <td>{r.ad_budget_level}</td>
                  <td className="ta-r">{usd(r.cost_attributed_usd)}</td>
                  <td className="ta-r">{r.lead_score}</td>
                  <td className="ta-r">
                    <span className={r.converted_to_sale ? "flag flag--yes" : "flag"}>
                      {r.converted_to_sale ? "Sí" : "No"}
                    </span>
                  </td>
                  <td className="ta-r">{usd(r.revenue_usd)}</td>
                  <td className={`ta-r ${Number(r.contribution_profit_usd) < 0 ? "neg" : ""}`}>
                    {usd(r.contribution_profit_usd)}
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
