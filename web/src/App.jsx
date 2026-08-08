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
import "./styles/global.css";

const PHASE_LABEL = {
  ingesta: "Fase 02 · 20.000 ventanas de despacho",
  uplift: "Fase 03 · Qué aporta cada palanca",
  montecarlo: "Fase 04 · 10.000 futuros",
  reporte: "Fase 05 · La decisión, en dólares",
};

const FAQ = [
  {
    q: "¿Por qué miles de escenarios y no una predicción?",
    a: "Una predicción puntual esconde el riesgo. Al simular miles de futuros con ruido realista se obtiene la distribución completa: cuánto se gana en el peor caso, en la mediana y en el mejor, y con qué probabilidad se pierde dinero.",
  },
  {
    q: "¿Qué es el uplift contrafactual?",
    a: "Es la diferencia entre lo que se espera de una ventana de despacho tal como está y lo que se esperaría si se cambiara una palanca concreta (profundidad de descarga, ventana de carga, producto de mercado), manteniendo todo lo demás igual.",
  },
  {
    q: "¿De dónde salen los datos?",
    a: "De 20.000 ventanas horarias de despacho ya ejecutadas. Es un caso sintético: los datos se generan con distribuciones coherentes con el dominio, no se descargan de ningún operador de red real. Los modelos aprenden de lo que pasó cuando se movió cada palanca, no de supuestos inventados en una hoja de cálculo.",
  },
  {
    q: "¿Por qué gana la opción menos espectacular?",
    a: "Porque el desgaste de las celdas crece más que proporcionalmente con la profundidad de descarga. La estrategia que más energía mueve factura más y deja menos: compra ingreso de hoy pagándolo con vida útil que no se recupera. La decisión correcta es la de mayor esperanza ajustada al riesgo, no la de mayor techo.",
  },
  {
    q: "¿La simulación corre de verdad o es una animación?",
    a: "Corre en el backend de Python. El progreso que se ve en pantalla viene de un endpoint real que reporta escenarios completados, no de un temporizador de la interfaz.",
  },
];

export default function App() {
  const [payload, setPayload] = useState(null);
  const [phase, setPhase] = useState("ingesta");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/payload")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setPayload(d.payload))
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
        solid="El histórico de despacho"
        ghost="es la única fuente de verdad."
        echo="Sin diversidad real no hay modelo, hay memorización."
        copy="Antes de modelizar hay que comprobar que el histórico cubre condiciones diversas: bloques horarios, productos de mercado, nodos de red y una ventana temporal suficiente para que el modelo aprenda de algo más que del ruido de un trimestre."
        wide
        media={<DatasetSection payload={payload} />}
      />

      <Feature
        id="fase-02"
        index={3}
        eyebrow={f("uplift")?.eyebrow}
        faseTitulo={f("uplift")?.title}
        solid="Dos modelos"
        ghost="estiman el impacto de cada palanca."
        echo="El uplift no es una opinión, es una diferencia medida."
        copy="Una regresión logística estima si el ciclo cubrirá su coste de degradación; un gradient boosting estima el ingreso esperado. La diferencia contra el escenario base es el uplift contrafactual de mover esa palanca y nada más."
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
        echo="Un número esconde el riesgo. Una distribución lo enseña."
        copy="La simulación inyecta incertidumbre en los parámetros, riesgo de ejecución y ruido residual. El resultado no es un número: es una distribución con suelo, techo y probabilidad de perder dinero."
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
        echo="Mismo dato, tres decisiones distintas."
        copy="El mismo resultado interpretado desde tres ángulos: retorno sobre el capital, vida útil del activo y control del escenario adverso. No es un resumen distinto del mismo texto, es una decisión distinta con el mismo dato."
        wide
        media={<ReportSection payload={payload} />}
      />
      )}

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
