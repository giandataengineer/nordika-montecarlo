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
    a: "Una predicción puntual oculta el riesgo. Diez mil escenarios con incertidumbre realista dan la distribución completa: el suelo, la mediana, el techo y con qué probabilidad se pierde dinero. El presupuesto se compromete una sola vez, no cien.",
  },
  {
    q: "¿Qué es el uplift contrafactual?",
    a: "La diferencia entre el resultado esperado de una oportunidad tal como se registró y el que cabría esperar cambiando una sola palanca. Esa segunda versión no existe en el histórico, así que se estima con los modelos entrenados sobre los casos en los que sí se movió esa palanca.",
  },
  {
    q: "¿La simulación se ejecuta de verdad?",
    a: "Sí. Los modelos se entrenan en Python y su resultado se exporta al navegador, donde se calculan el remuestreo y los tres ruidos escenario a escenario. El progreso en pantalla son escenarios completados, no un temporizador.",
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
        echo="Sin diversidad real no hay modelo: hay memorización."
        copy="Antes de modelizar es necesario comprobar que el histórico recoge condiciones suficientemente diversas. Se revisan los canales, las campañas, los segmentos de cliente, las geografías y la ventana temporal cubierta, de manera que el modelo aprenda del comportamiento del negocio y no del ruido de un único trimestre."
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
        echo="El uplift no es una opinión, es una diferencia medida."
        copy="Una regresión logística estima la probabilidad de que la oportunidad convierta y un gradient boosting estima el ingreso esperado cuando lo hace. La diferencia entre el escenario base y el escenario con la palanca modificada es el uplift contrafactual de esa palanca, aislado del resto de factores."
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
        echo="Un valor único esconde el riesgo. Una distribución lo muestra."
        copy="La simulación incorpora tres fuentes de incertidumbre: la variabilidad de los parámetros estimados, el riesgo de que la iniciativa no llegue a ejecutarse por completo y el error residual del modelo. El resultado no es una cifra, sino una distribución con suelo, techo y probabilidad de pérdida."
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
        copy="El mismo resultado se interpreta desde tres ángulos: el retorno sobre el capital invertido, el aprendizaje que deja la palanca para los trimestres siguientes y el control del escenario adverso. No son tres resúmenes del mismo texto, sino tres lecturas que pueden no coincidir."
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
        meta={summary ? `${summary.period_start} - ${summary.period_end} · ${fmtInt(summary.rows)} registros` : "Decision Intelligence"}
      />
    </div>
  );
}
