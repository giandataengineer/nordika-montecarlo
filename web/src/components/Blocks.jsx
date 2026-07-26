import BorderGlow from "../reactbits/BorderGlow";
import CountUp from "../reactbits/CountUp";

/* Piezas compartidas por las cuatro fases. Mismo vocabulario visual en todas:
   corner brackets, etiqueta mono arriba, cifra grande, glosa debajo. */

export function Panel({ title, eyebrow, children, dark, className = "" }) {
  return (
    <BorderGlow
      className={`panel ${dark ? "panel--dark" : ""} ${className}`}
      backgroundColor={dark ? "#1c1c1c" : "#faf9f5"}
      borderRadius={22}
      colors={["#d9531e", "#7c3aed", "#2f80ed"]}
      animated={false}
    >
      <span className="card__bracket card__bracket--tl" aria-hidden="true" />
      <span className="card__bracket card__bracket--br" aria-hidden="true" />
      {eyebrow && <span className="label panel__eyebrow">{eyebrow}</span>}
      {title && <h3 className="panel__title">{title}</h3>}
      {children}
    </BorderGlow>
  );
}

/* Tarjeta de métrica: cifra dominante + qué significa, como en el dashboard
   original. La glosa es lo que la diferencia de un KPI decorativo. */
export function Metric({ label, value, gloss, animate, accent }) {
  return (
    <div className={`metric ${accent ? "metric--accent" : ""}`}>
      <span className="label">{label}</span>
      <strong className="metric__value">
        {animate ? <CountUp to={Number(value) || 0} separator="," duration={1.6} /> : value}
      </strong>
      {gloss && <span className="metric__gloss">{gloss}</span>}
    </div>
  );
}

export function MetricGrid({ children, cols }) {
  return (
    <div className="metric-grid" style={cols ? { "--cols": cols } : undefined}>
      {children}
    </div>
  );
}

/* Barra horizontal con recuento a la derecha: bandas de error, distribuciones. */
export function BarRow({ label, gloss, value, max, count, tone }) {
  const w = max ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div className="bar-row">
      <div className="bar-row__head">
        <span className="bar-row__label">{label}</span>
        {gloss && <span className="bar-row__gloss">{gloss}</span>}
      </div>
      <div className="bar-row__track">
        <i style={{ width: `${w}%`, background: tone || "var(--accent)" }} />
      </div>
      <span className="bar-row__count">{count}</span>
    </div>
  );
}

export function Bullets({ items, icon: Icon, tone }) {
  if (!items?.length) return null;
  return (
    <ul className="bullets">
      {items.map((t) => (
        <li key={t}>
          {Icon && <Icon className="bullets__icon" style={tone ? { color: tone } : undefined} />}
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

export function Chips({ items }) {
  if (!items?.length) return null;
  return (
    <div className="chips">
      {items.map((t) => {
        const ok = /pass/i.test(t);
        return (
          <span className={`chip ${ok ? "chip--ok" : ""}`} key={t}>
            {t}
          </span>
        );
      })}
    </div>
  );
}
