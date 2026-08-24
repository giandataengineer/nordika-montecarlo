import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Bullets, Chips, Metric, MetricGrid, Panel } from "./Blocks";
import { pct, roi, usd } from "../lib/format";
import { IconAlert, IconArrowRight, IconCheck, IconDecide, IconLayers, IconTrendUp } from "./Icons";
import { Consenso } from "./Consenso";

const ROLES = [
  { key: "ceo", label: "CEO", lead: "Prioriza asignación de capital, payback y claridad de decisión ejecutiva." },
  { key: "growth", label: "Growth", lead: "Prioriza velocidad de aprendizaje, iteración y escalado de canales." },
  { key: "riesgo", label: "Riesgo", lead: "Prioriza el control del downside, la robustez del suelo y los criterios de contención." },
];

export function ReportSection({ payload }) {
  const rec = payload?.recommendation;
  const report = payload?.report;
  const [role, setRole] = useState("ceo");

  if (!rec) return <Panel dark>Consolidando informe...</Panel>;

  const v = rec.audience_views?.[role] ?? {};
  const meta = ROLES.find((r) => r.key === role);

  return (
    <div className="stack">
      <MetricGrid cols={4}>
        <Metric label="Decisión recomendada" value={rec.decision} gloss="Alternativa con mejor esperanza ajustada a riesgo" accent />
        <Metric label="Beneficio esperado" value={usd(rec.expected_profit_usd)} gloss="Mediana de los escenarios simulados" />
        <Metric label="ROI esperado" value={roi(rec.expected_roi)} gloss="Retorno sobre la inversión comprometida" />
        <Metric label="Probabilidad de pérdida" value={pct(rec.probability_loss)} gloss="Escenarios en los que se pierde dinero" />
      </MetricGrid>

      <Consenso payload={payload} />

      <div className="split-wide">
        <Panel eyebrow="Recomendación final · selecciona enfoque de lectura">
          <div className="role-tabs" role="tablist">
            {ROLES.map((r) => (
              <button
                key={r.key}
                role="tab"
                aria-selected={role === r.key}
                className={`role-tab ${role === r.key ? "is-on" : ""}`}
                onClick={() => setRole(r.key)}
              >
                {r.label}
              </button>
            ))}
          </div>

          <p className="role-lead">{meta.lead}</p>

          <AnimatePresence mode="wait">
            <motion.div
              key={role}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <h3 className="verdict">{v.headline}</h3>
              <p className="verdict__summary">{v.summary}</p>

              <div className="verdict__cols">
                <section>
                  <h4 className="label">Por qué gana</h4>
                  <Bullets items={v.reasons} icon={IconCheck} tone="var(--green)" />
                </section>
                <section>
                  <h4 className="label">Qué vigilar</h4>
                  <Bullets items={v.watchouts} icon={IconAlert} tone="var(--orange)" />
                </section>
                <section>
                  <h4 className="label">Siguientes pasos</h4>
                  <Bullets items={v.next_actions} icon={IconArrowRight} tone="var(--blue)" />
                </section>
                <section>
                  <h4 className="label">Señales para rotar la apuesta</h4>
                  <Bullets items={v.switch_signals} icon={IconTrendUp} tone="var(--purple)" />
                </section>
              </div>

              <section className="verdict__dd">
                <h4 className="label">Preguntas antes de ejecutar</h4>
                <Bullets items={v.due_diligence} icon={IconLayers} tone="var(--faint)" />
              </section>
            </motion.div>
          </AnimatePresence>
        </Panel>

        <div className="stack">
          <Panel eyebrow="Riesgos y siguientes pasos" title="Puntos de control para la decisión">
            <Bullets items={rec.watchouts} icon={IconAlert} tone="var(--orange)" />
            {report?.checks && (
              <>
                <h4 className="label" style={{ display: "block", margin: "22px 0 12px" }}>Validaciones</h4>
                <Chips items={report.checks} />
              </>
            )}
          </Panel>

          <Panel eyebrow="Hallazgos adicionales" title="Lecturas complementarias">
            <Bullets items={rec.findings} icon={IconCheck} tone="var(--blue)" />
          </Panel>
        </div>
      </div>

      <div className="split-2">
        <Panel eyebrow="Consultas realizadas" title="Huella de herramientas">
          <p className="panel__copy">
            El agente no responde de memoria: cada afirmación viene de una consulta concreta
            sobre los resultados del simulador y de los modelos.
          </p>
          <div className="trace-list">
            {(rec.tool_trace ?? []).map((t) => (
              <article className="trace" key={t.name + t.outcome}>
                <div className="trace__head">
                  <code>{t.name}</code>
                  {t.args && <span className="label">{Object.entries(t.args).map(([k, x]) => `${k}=${x}`).join(" · ")}</span>}
                </div>
                <p className="trace__purpose">{t.purpose}</p>
                <p className="trace__outcome">{t.outcome}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel eyebrow="Metodología" title="Notas del analista">
          <Bullets items={report?.executive_notes} icon={IconDecide} tone="var(--purple)" />
        </Panel>
      </div>
    </div>
  );
}
