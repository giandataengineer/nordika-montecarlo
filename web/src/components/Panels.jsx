import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import CountUp from "../reactbits/CountUp";
import DecryptedText from "../reactbits/DecryptedText";
import BorderGlow from "../reactbits/BorderGlow";
import AnimatedList from "../reactbits/AnimatedList";
import Carousel from "../reactbits/Carousel";
import { IconAlert, IconCheck, IconDecide, IconLayers, IconSpread, IconTrendUp } from "./Icons";

const usd = (n) => `$${Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const pct = (n) => `${(Number(n || 0) * 100).toFixed(1)}%`;

/* Tarjeta con corner brackets y borde que se ilumina siguiendo al cursor.
   Los brackets en L son el detalle editorial recurrente de legend. */
function Card({ title, children, dark }) {
  return (
    <BorderGlow
      className={dark ? "card card--dark" : "card"}
      backgroundColor={dark ? "#1c1c1c" : "#faf9f5"}
      borderRadius={22}
      colors={["#d9531e", "#7c3aed", "#2f80ed"]}
    >
      <span className="card__bracket card__bracket--tl" aria-hidden="true" />
      <span className="card__bracket card__bracket--br" aria-hidden="true" />
      {title && <h3 className="card__title">{title}</h3>}
      {children}
    </BorderGlow>
  );
}

function Stat({ label, value, animate }) {
  return (
    <div className="stat">
      <span className="stat__value">
        {animate ? <CountUp to={Number(value) || 0} separator="," duration={1.8} /> : value}
      </span>
      <span className="label">{label}</span>
    </div>
  );
}

export function DatasetPanel({ payload }) {
  const s = payload?.dataset?.summary;
  if (!s) return <Card>Cargando base histórica...</Card>;
  return (
    <Card>
      <div className="stat-row">
        <Stat label="Campañas" value={s.campaign_count} animate />
        <Stat label="Variables" value={s.variable_count} animate />
        <Stat label="Segmentos" value={s.segment_count} animate />
        <Stat label="Geografías" value={s.geography_count} animate />
      </div>
      <span className="card__foot label">
        <DecryptedText
          text={`${s.period_start} → ${s.period_end} · conversión ${pct(s.conversion_rate)} · ticket ${usd(s.avg_ticket_usd)}`}
          animateOn="view"
          speed={22}
          sequential
          revealDirection="start"
        />
      </span>
    </Card>
  );
}

export function UpliftPanel({ payload }) {
  const rows = payload?.uplift?.main ?? [];
  if (!rows.length) return <Card dark>Calculando uplift...</Card>;
  return (
    <Card dark>
      <ul className="lever-list">
        {rows.slice(0, 4).map((r) => (
          <li className="lever" key={r.label}>
            <IconLayers className="lever__icon" />
            <span className="lever__name">{r.label}</span>
            <span className="lever__value">
              {pct(r.baseline_cobertura)} → {pct(r.scenario_conversion)}
            </span>
          </li>
        ))}
      </ul>
      <span className="card__foot label">
        Uplift contrafactual estimado por ML, no por A/B real
      </span>
    </Card>
  );
}

export function SimulationPanel({ payload }) {
  const rows = payload?.simulation?.summary ?? [];
  if (!rows.length) return <Card>Preparando simulación...</Card>;
  const data = rows.map((r) => ({
    name: r.decision,
    beneficio: Number(r.expected_profit_usd ?? 0),
    perdida: Number(r.probability_loss ?? 0),
  }));

  /* Ranking en lista animada: cada fila entra con su propio retardo. */
  const ranking = rows.map(
    (r, i) =>
      `${String(i + 1).padStart(2, "0")} · ${r.decision} - ${usd(r.expected_profit_usd)} · pérdida ${pct(r.probability_loss)}`
  );

  return (
    <Card>
      <div className="stat-row" style={{ marginBottom: 22 }}>
        <Stat label="Escenarios" value={payload?.simulation?.total_simulations ?? 0} animate />
        <Stat label="Estrategias" value={rows.length} animate />
      </div>

      <div className="chart">
        <ResponsiveContainer width="100%" height={210}>
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 16 }}>
            <CartesianGrid stroke="var(--line)" horizontal={false} />
            <XAxis
              type="number"
              stroke="var(--faint)"
              tick={{ fontSize: 12 }}
              tickFormatter={(v) => `$${Math.round(v / 1000)}k`}
            />
            <YAxis type="category" dataKey="name" width={150} stroke="var(--faint)" tick={{ fontSize: 12 }} />
            <Tooltip
              cursor={{ fill: "rgba(19,19,19,0.04)" }}
              formatter={(v) => usd(v)}
              contentStyle={{ background: "var(--panel-warm)", border: "1px solid var(--line)", borderRadius: 10 }}
            />
            <Bar dataKey="beneficio" radius={[0, 4, 4, 0]} animationDuration={1200}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.perdida > 0.2 ? "var(--ghost)" : "var(--accent)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="rank-list">
        <AnimatedList items={ranking} showGradients enableArrowNavigation={false} displayScrollbar={false} />
      </div>

      <span className="card__foot label">
        <IconSpread style={{ width: 13, height: 13, verticalAlign: "-2px", marginRight: 8 }} />
        En gris, las iniciativas con probabilidad de pérdida superior al 20 %
      </span>
    </Card>
  );
}

export function ReportPanel({ payload }) {
  const rec = payload?.recommendation;
  if (!rec) return <Card dark>Consolidando informe...</Card>;

  /* Las tres lecturas del mismo resultado, en carrusel arrastrable. */
  const roles = [
    {
      id: 1,
      icon: <IconDecide />,
      title: "Dirección",
      description: `${usd(rec.expected_profit_usd)} de beneficio esperado, ROI ${Number(rec.expected_roi).toFixed(1)}x y ${pct(rec.probability_loss)} de probabilidad de pérdida.`,
    },
    {
      id: 2,
      icon: <IconTrendUp />,
      title: "Crecimiento",
      description: `La ventaja frente a la segunda opción es de ${usd(rec.gap_vs_second_usd)}: la decisión no depende de un empate estadístico.`,
    },
    {
      id: 3,
      icon: <IconAlert />,
      title: "Riesgo",
      description:
        "El uplift se estimó por contrafactual sobre un histórico sintético. Antes de extrapolar el resultado es necesario validarlo con una prueba A/B real.",
    },
  ];

  return (
    <Card dark title={rec.decision}>
      <div className="stat-row">
        <div className="stat">
          <span className="stat__value">{usd(rec.expected_profit_usd)}</span>
          <span className="label">Beneficio esperado</span>
        </div>
        <div className="stat">
          <span className="stat__value">{pct(rec.probability_loss)}</span>
          <span className="label">Probabilidad de pérdida</span>
        </div>
      </div>

      <div className="roles-carousel">
        <Carousel items={roles} baseWidth={290} autoplay autoplayDelay={4200} pauseOnHover loop />
      </div>

      <ul className="lever-list" style={{ marginTop: 22 }}>
        <li className="lever">
          <IconCheck className="lever__icon" style={{ color: "var(--green)" }} />
          <span>Suelo del escenario (P10) por encima de las alternativas</span>
        </li>
        <li className="lever">
          <IconAlert className="lever__icon" style={{ color: "var(--orange)" }} />
          <span>Re-simular tras el piloto antes de extender</span>
        </li>
      </ul>
    </Card>
  );
}
