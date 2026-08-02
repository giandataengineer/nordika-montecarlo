import { useMemo, useState } from "react";
import Counter from "../reactbits/Counter";
import { IconTrendUp } from "./Icons";

const RANGES = ["P10", "P50", "P90"];
const usd = (n) => Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

/* Histograma sintético estable: la misma semilla da siempre la misma forma,
   así el mockup no parpadea entre renders. La forma es decorativa; las cifras
   que rodea salen todas del payload real. */
function bars(seed, n = 34) {
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const x = (i / (n - 1)) * 2 - 1;
    const bell = Math.exp(-(x * x) / 0.24);
    const jitter = Math.sin(seed + i * 1.7) * 0.08;
    out.push(Math.max(0.05, Math.min(1, bell + jitter)));
  }
  return out;
}

const SEEDS = { ingesta: 1.2, uplift: 3.4, montecarlo: 5.6, reporte: 7.8 };

export function Console({ summary, top, totalSims, phase }) {
  const [range, setRange] = useState("P50");

  const data = useMemo(() => bars(SEEDS[phase] ?? 1.2), [phase]);
  const peak = data.indexOf(Math.max(...data));

  const shown = { P10: top?.p10_usd, P50: top?.p50_usd, P90: top?.p90_usd }[range];

  return (
    <article className="console">
      <div className="console__head">
        <h3>{top ? top.decision : "Beneficio esperado"}</h3>
        <span className="label">{usd(totalSims)} escenarios</span>
      </div>

      {/* odómetro: los dígitos giran al cambiar de percentil */}
      <div className="console__odo">
        <span className="console__odo-unit">$</span>
        {top ? (
          <Counter
            value={Math.round(shown || 0)}
            fontSize={40}
            gap={1}
            horizontalPadding={0}
            borderRadius={0}
            fontWeight={500}
            gradientHeight={0}
            gradientFrom="transparent"
            gradientTo="transparent"
          />
        ) : (
          <span className="console__odo-empty">-</span>
        )}
      </div>

      <span className="console__delta">
        <IconTrendUp />
        {top
          ? `ROI ${top.expected_roi.toFixed(1)}x · pérdida ${(top.probability_loss * 100).toFixed(1)} %`
          : "Esperando backend"}
      </span>

      <div className="console__bars">
        {data.map((h, i) => (
          <i
            key={i}
            data-hot={i === peak}
            style={{ height: `${h * 100}%`, animationDelay: `${i * 0.018}s` }}
          />
        ))}
      </div>

      <div className="console__range">
        {RANGES.map((r) => (
          <button key={r} type="button" aria-pressed={r === range} onClick={() => setRange(r)}>
            {r}
          </button>
        ))}
      </div>

      {top && (
        <div className="console__block">
          <div className="console__block-row">
            <span className="label">Suelo P10</span>
            <b>${usd(top.p10_usd)}</b>
          </div>
        </div>
      )}

      {summary && (
        <div className="console__block">
          <div className="console__block-row">
            <span className="label">Conversión observada</span>
            <b>{(summary.conversion_rate * 100).toFixed(1)} %</b>
          </div>
          <div className="console__meter">
            <i style={{ width: `${Math.min(100, summary.conversion_rate * 100 * 6)}%` }} />
          </div>
        </div>
      )}

      {summary && (
        <p className="label" style={{ display: "block", marginTop: 16 }}>
          Energía media {summary.avg_ticket_usd?.toFixed(1)} MWh · {usd(summary.rows)} ventanas
        </p>
      )}
    </article>
  );
}
