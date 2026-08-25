import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarRow, Metric, MetricGrid, Panel } from "./Blocks";
import { pct, pctRaw, usd } from "../lib/format";

export function ModelsSection({ payload }) {
  const c = payload?.models?.classification;
  const r = payload?.models?.regression;
  const main = payload?.uplift?.main ?? [];
  const ads = payload?.uplift?.ads ?? [];

  if (!c || !r) return <Panel>Entrenando modelos...</Panel>;

  /* Gain chart: capture acumulada del modelo contra la diagonal aleatoria.
     La distancia entre ambas curvas es lo que aporta el modelo. */
  const gain = [{ pop: 0, capt: 0, base: 0 }].concat(
    c.gain_chart.map((g) => ({
      pop: Number(g.population_pct) * 100,
      capt: Number(g.capture_pct) * 100,
      base: Number(g.population_pct) * 100,
      decile: g.decile,
      conv: Number(g.conversion_rate) * 100,
    }))
  );
  const topDecile = c.gain_chart[0];
  const maxBand = Math.max(...r.residual_bands.map((b) => b.count));

  const lever = (u, tone) => (
    <article className="lever-card" key={u.parameter}>
      <span className="label">{u.label}</span>
      <p className="lever-card__delta">
        {pct(u.baseline_cobertura)} <span className="lever-card__arrow">→</span>{" "}
        <b style={{ color: tone }}>{pct(u.scenario_conversion)}</b> de cobertura esperada
      </p>
      {u.description && <p className="lever-card__copy">{u.description}</p>}
      <div className="lever-card__foot">
        <span>
          Uplift <b>{pctRaw(Number(u.conversion_lift_pct) * 100)}</b>
        </span>
        <span>
          Impacto por oportunidad <b>{usd(u.profit_lift_per_window_usd, 2)}</b>
          {u.profit_lift_ci_low_usd != null && (
            <em className="ci">
              IC 90% [{usd(u.profit_lift_ci_low_usd, 2)} - {usd(u.profit_lift_ci_high_usd, 2)}]
              {u.profit_lift_significativo ? "" : " · cruza el cero"}
            </em>
          )}
        </span>
        <span>
          Muestra <b>{Number(u.sample_size).toLocaleString("en-US")}</b>
        </span>
      </div>
      <div className="lever-card__track">
        <i
          style={{
            width: `${Math.min(100, Math.abs(Number(u.conversion_lift_pct)) * 180)}%`,
            background: tone,
          }}
        />
      </div>
    </article>
  );

  return (
    <div className="stack">
      <div className="split-2">
        <Panel eyebrow="Modelo 01" title={`${c.name} para probabilidad de éxito`}>
          <p className="panel__copy">{c.purpose}</p>
          <MetricGrid cols={4}>
            <Metric label="AUC" value={c.auc.toFixed(3)} gloss="Capacidad de separar oportunidades con mayor y menor probabilidad de éxito" accent />
            <Metric label="Base de cobertura" value={pct(c.positive_rate)} gloss="Oportunidades que convirtieron en validación" />
            <Metric label="Probabilidad media" value={pct(c.avg_predicted_prob)} gloss="Propensión media estimada por el modelo" />
            <Metric label="Top decil" value={pct(topDecile.conversion_rate)} gloss="Conversión del 10% de oportunidades con mayor probabilidad estimada" />
          </MetricGrid>

          <div className="chart-head">
            <span className="label">Captura acumulada de conversiones</span>
            <span className="label">Gain chart</span>
          </div>
          <div className="chart">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={gain} margin={{ left: 0, right: 8, top: 8 }}>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey="pop" stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                <YAxis stroke="var(--faint)" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} width={46} />
                <Tooltip
                  formatter={(v, k) => [`${Number(v).toFixed(1)}%`, k === "capt" ? "Modelo" : "Aleatorio"]}
                  labelFormatter={(v) => `Top ${v}% de la población`}
                  contentStyle={{ background: "var(--panel-warm)", border: "1px solid var(--line)", borderRadius: 10 }}
                />
                <Line type="monotone" dataKey="capt" stroke="var(--purple)" strokeWidth={2.2} dot={{ r: 3 }} animationDuration={1600} />
                <Line type="monotone" dataKey="base" stroke="var(--faint)" strokeWidth={1.4} strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="chart-lectura">
            La diagonal es lo que se captura eligiendo oportunidades al azar. La curva
            es lo que se captura siguiendo el orden del modelo. Cuanto más se separan en
            el tramo izquierdo, más conversiones caen dentro del primer decil y menos
            esfuerzo cuesta alcanzarlas.
          </p>
        </Panel>

        <Panel eyebrow="Modelo 02" title={`${r.name} para valor esperado`}>
          <p className="panel__copy">{r.purpose}</p>
          <MetricGrid cols={4}>
            <Metric label="MAE" value={usd(r.mae_usd)} gloss="Error absoluto medio sobre el valor estimado" accent />
            <Metric label="R²" value={r.r2.toFixed(3)} gloss="Capacidad del modelo para explicar la variación del ingreso" />
            <Metric label="Sesgo medio" value={usd(r.mean_residual_usd)} gloss="Diferencia media entre valor real y valor estimado" />
            <Metric label="P90 error" value={usd(r.p90_abs_error_usd)} gloss="Error absoluto en el percentil 90" />
          </MetricGrid>

          <div className="chart-head">
            <span className="label">Distribución del error</span>
            <span className="label">Observaciones por banda</span>
          </div>
          <div className="bands">
            {r.residual_bands.map((b) => (
              <BarRow
                key={b.label}
                label={b.label}
                gloss="Número de observaciones dentro de esta banda de error"
                value={b.count}
                max={maxBand}
                count={b.count}
                tone={/infra|sobre/i.test(b.label) ? "var(--orange)" : "var(--green)"}
              />
            ))}
          </div>
        </Panel>
      </div>

      <Panel eyebrow="Palancas de negocio" title="Escenarios con mayor uplift esperado">
        <p className="panel__copy">
          Las iniciativas mejor posicionadas según el contrafactual, ordenadas por la
          conversión que añaden y por el margen que dejan en cada oportunidad. El uplift
          sale de comparar cada oportunidad consigo misma después de cambiarle una sola
          palanca, así que ninguna de estas cifras está puesta a mano.
        </p>
        <div className="lever-grid">{main.map((u) => lever(u, "var(--purple)"))}</div>
      </Panel>

      {ads.length > 0 && (
        <Panel eyebrow="Sensibilidad" title="Qué pasa al mover la inversión en Ads">
          <p className="panel__copy">
            El retorno de la inversión publicitaria no es lineal, porque al escalarla
            aparece la saturación de la audiencia. Estos escenarios muestran hasta qué
            tramo de inversión sigue compensando el gasto.
          </p>
          <div className="lever-grid">{ads.map((u) => lever(u, "var(--blue)"))}</div>
        </Panel>
      )}
    </div>
  );
}
