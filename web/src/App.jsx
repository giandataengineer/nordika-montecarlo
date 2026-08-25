import { useCallback, useEffect, useState } from "react";
import { useSimulacion } from "./hooks/useSimulacion";
import { fases as leerFases } from "./lib/fases";
import { TopBar } from "./components/TopBar";
import { Hero } from "./components/Hero";
import { Feature } from "./components/Feature";
import { Platform } from "./components/Platform";
import { Accordion } from "./components/Accordion";
import { Footer } from "./components/Footer";
import { DatasetSection } from "./components/DatasetSection";
import { ModelsSection } from "./components/ModelsSection";
import { LiveSimulation } from "./components/LiveSimulation";
import { ReportSection } from "./components/ReportSection";
import { RobustezSection } from "./components/RobustezSection";
import { ProblemaSection } from "./components/ProblemaSection";
import { Respuestas } from "./components/Respuestas";
import { SqlSection } from "./components/SqlSection";
import "./styles/global.css";

const PHASE_LABEL = {
  ingesta: "Fase 02 · 20.000 oportunidades",
  uplift: "Fase 03 · Qué aporta cada palanca",
  montecarlo: "Fase 04 · 10.000 futuros",
  reporte: "Fase 05 · La decisión, en dólares",
};

const FAQ = [
  {
    q: "¿Por qué simular y no predecir?",
    a: "Una predicción sola no dice cuánto puedes perder. Con diez mil escenarios sale la distribución entera: el suelo, la mediana, el techo y cada cuántas veces la cosa acaba en rojo. Y el presupuesto se firma una vez, no cien."
  },
  {
    q: "¿Qué es el uplift contrafactual?",
    a: "La diferencia entre lo que se espera de una oportunidad tal como quedó registrada y lo que se esperaría cambiándole una sola palanca. Esa segunda versión no está en ningún sitio, así que la estiman los modelos, entrenados con los casos en los que esa palanca sí se movió."
  },
  {
    q: "¿La simulación se ejecuta de verdad?",
    a: "Sí. Los modelos se entrenan en Python y el resultado se exporta al navegador, que hace el remuestreo y los tres ruidos escenario a escenario. Lo que marca la barra son escenarios ya terminados, no un temporizador."
  },
];

export default function App() {
  const [payload, setPayload] = useState(null);
  const [phase, setPhase] = useState("ingesta");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("payload.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setPayload(d))
      .catch((e) => setError(e.message));
  }, []);

  const handlePhase = useCallback((p) => setPhase(p), []);
  // Un solo estado de simulación para toda la pagina: las fases que dependen de
  // los escenarios no se muestran hasta que hay escenarios de verdad.
  const sim = useSimulacion(payload?.simulation?.total_simulations ?? 10000);

  const summary = payload?.dataset?.summary;
  const fmtInt = (n) => Number(n || 0).toLocaleString("en-US");
  const totalSims = payload?.simulation?.total_simulations;
  const listaFases = leerFases(payload);
  const f = (k) => listaFases.find((x) => x.key === k);

  return (
    <div className="page" data-phase={phase}>
      <TopBar
        error={error}
        stats={summary ? `${fmtInt(summary.rows)} registros · ${fmtInt(totalSims)} escenarios simulados` : "Cargando base histórica"}
        fases={listaFases}
      />

      <Hero
        summary={summary}
        top={payload?.simulation?.summary?.[0]}
        totalSims={payload?.simulation?.total_simulations}
        fase={f("briefing")}
        onPhaseChange={handlePhase}
      />

      <ProblemaSection fase={f("briefing")} summary={summary} ranking={payload?.simulation?.summary ?? []} />

      <Feature
        id="fase-01"
        index={2}
        eyebrow={f("ingesta")?.eyebrow}
        faseTitulo={f("ingesta")?.title}
        solid="El histórico comercial"
        ghost="es la única fuente de verdad."
        echo="Si el histórico solo cubre un trimestre, el modelo memoriza ese trimestre."
        copy="Antes de modelizar hay que mirar si el histórico da para tanto. Se revisan canales, campañas, segmentos, geografías y cuánto periodo cubre. Si toda la variedad se concentra en unos pocos meses, el modelo aprende de esos meses y no del negocio."
        wide
        media={<DatasetSection payload={payload} />}
      />

      <SqlSection payload={payload} />

      <Feature
        id="fase-02"
        index={3}
        eyebrow={f("uplift")?.eyebrow}
        faseTitulo={f("uplift")?.title}
        solid="Dos modelos"
        ghost="estiman el impacto de cada palanca."
        echo="El uplift se mide, no se supone."
        copy="Una regresión logística estima la probabilidad de que la oportunidad convierta. Un gradient boosting estima cuánto factura si convierte. Se cambia una palanca, se vuelve a preguntar, y la diferencia entre las dos respuestas es lo que aporta esa palanca con todo lo demás quieto."
        wide
        media={<ModelsSection payload={payload} />}
      />

      <Platform />

      <Feature
        id="fase-03"
        index={4}
        eyebrow={f("montecarlo")?.eyebrow}
        faseTitulo={f("montecarlo")?.title}
        solid={totalSims ? `${fmtInt(totalSims)} futuros` : "Miles de futuros"}
        ghost="en vez de una sola predicción."
        echo="Con un solo número no se ve el riesgo. Con diez mil, sí."
        copy="La simulación mete tres fuentes de incertidumbre: lo que varían los parámetros estimados, el riesgo de que la iniciativa se quede a medias y el error que el modelo no explica. Al final no sale una cifra. Sale una distribución, con su suelo, su techo y su probabilidad de perder dinero."
        wide
        media={
          <>
            <LiveSimulation payload={payload} sim={sim} />
            {sim.lista && <div id="robustez"><RobustezSection payload={payload} /></div>}
          </>
        }
      />

            {sim.lista && (
      <Feature
        id="fase-04"
        index={5}
        eyebrow={f("reporte")?.eyebrow}
        faseTitulo={f("reporte")?.title}
        solid="La recomendación"
        ghost="cambia según quién la lea."
        echo="Mismas cifras, tres criterios distintos."
        copy="Las mismas cifras leídas desde tres sitios: el retorno sobre el capital, el aprendizaje que deja la palanca para los trimestres que vienen y el control del peor escenario. Tres lecturas que pueden no coincidir, y cuando no coinciden eso también es información."
        wide
        media={<ReportSection payload={payload} />}
      />
      )}

      {sim.lista && <Respuestas payload={payload} />}

      <section className="section" id="faq">
        <div className="shell section__inner faq__grid">
          <div>
            <span className="label" style={{ display: "block", marginBottom: 24 }}>FAQ</span>
            <h2 className="display faq__title">
              Cómo leer<br />estos números.
            </h2>
          </div>
          <Accordion items={FAQ} />
        </div>
      </section>

      <Footer
        fases={listaFases}
        meta={summary ? `${summary.period_start} - ${summary.period_end} · ${fmtInt(summary.rows)} registros` : "Decisión Intelligence"}
      />
    </div>
  );
}
