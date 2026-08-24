import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import BlurText from "../reactbits/BlurText";
import LogoLoop from "../reactbits/LogoLoop";
import CountUp from "../reactbits/CountUp";
import Magnet from "../reactbits/Magnet";
import Dock from "../reactbits/Dock";
import Strands from "../reactbits/Strands";
import SpecularButton from "../reactbits/SpecularButton";
import StarBorder from "../reactbits/StarBorder";
import { Console } from "./Console";
import { IconArrowDown, IconBriefing, IconDecide, IconLoad, IconModel, IconSimulate } from "./Icons";

/* Los cuatro estados del hero. Cada uno cambia el acento de toda la página,
   el icono, la palabra destacada y las coordenadas. */
const STATES = [
  { key: "briefing", verb: "Presenta", tailKey: "caso", Icon: IconBriefing, coords: ["16.4090° S", "71.5375° O"] },
  { key: "ingesta", verb: "Carga", tailKey: "rows", Icon: IconLoad, coords: ["16.4090° S", "71.5375° O"] },
  { key: "uplift", verb: "Modela", tailKey: "vars", Icon: IconModel, coords: ["12.0464° S", "77.0428° O"] },
  { key: "montecarlo", verb: "Simula", tailKey: "sims", Icon: IconSimulate, coords: ["13.5320° S", "71.9675° O"] },
  { key: "reporte", verb: "Decide", tailKey: "roles", Icon: IconDecide, coords: ["8.1091° S", "79.0215° O"] },
];

/* Solo lo que el proyecto usa de verdad. Antes aparecian FastAPI y SciPy y
   ninguna de las dos esta importada en el codigo: el servidor es
   http.server de la biblioteca estandar y SciPy no se usa en ningun sitio.
   Afirmar una dependencia que no existe es lo primero que se cae si alguien
   abre el repositorio. */
const STACK = [
  "Python 3.14",
  "pandas",
  "NumPy",
  "scikit-learn",
  "LogisticRegression",
  "HistGradientBoosting",
  "Monte Carlo",
  "Uplift contrafactual",
  "Bootstrap IC",
  "EVPI",
  "OpenAI SDK",
  "Groq",
  "Gemini",
  "Mistral",
  "NVIDIA NIM",
  "OpenRouter",
  "Z.ai GLM",
  "http.server",
  "React 19",
  "Vite 6",
  "Recharts",
  "Motion",
  "OGL / WebGL",
  "GSAP",
];

const scrollTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });

export function Hero({ summary, top, totalSims, fase, onPhaseChange }) {
  const [i, setI] = useState(0);
  // al elegir una fase a mano se reinicia el ciclo, si no la rotación
  // automática podía saltar de inmediato a la siguiente
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % STATES.length), 3600);
    return () => clearInterval(id);
  }, [cycle]);

  const pick = (idx) => {
    setI(idx);
    setCycle((c) => c + 1);
  };

  useEffect(() => {
    onPhaseChange(STATES[i].key);
  }, [i, onPhaseChange]);

  const state = STATES[i];
  const Icon = state.Icon;

  // el pie del rotador sale del payload; sin backend no se inventa una cifra
  const n = (v) => Number(v || 0).toLocaleString("en-US");
  const tail = {
    rows: summary ? `${n(summary.rows)} registros` : "la base histórica",
    vars: summary ? `${n(summary.variable_count)} variables` : "cada palanca",
    sims: totalSims ? `${n(totalSims)} futuros` : "miles de futuros",
    roles: "desde 3 roles",
    caso: "el caso completo",
  }[state.tailKey];

  return (
    <section className="hero" id="top">
      {/* hebras WebGL de fondo, muy tenues: dan movimiento sin robar lectura */}
      <div className="hero__strands" aria-hidden="true">
        <Strands
          colors={["#d9531e", "#7c3aed", "#2f80ed", "#1fa971"]}
          count={4}
          speed={0.22}
          amplitude={0.75}
          waviness={1.3}
          thickness={0.45}
          glow={1.6}
          intensity={0.28}
          saturation={1.1}
          opacity={0.5}
          scale={1.9}
        />
      </div>

      <div className="shell hero__inner">
        <div className="hero__coords">
          <AnimatePresence mode="wait">
            <motion.span key={state.coords[0]} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
              {state.coords[0]}
            </motion.span>
          </AnimatePresence>
          <AnimatePresence mode="wait">
            <motion.span key={state.coords[1]} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
              {state.coords[1]}
            </motion.span>
          </AnimatePresence>
        </div>

        <h1 className="display hero__title">
          <BlurText text="Decide con datos." animateBy="words" delay={120} stepDuration={0.4} />
        </h1>

        <div className="hero__rotator">
          <AnimatePresence mode="wait">
            <motion.span
              key={state.key}
              className="hero__rotator-icon"
              initial={{ opacity: 0, scale: 0.6, rotate: -35 }}
              animate={{ opacity: 1, scale: 1, rotate: 0 }}
              exit={{ opacity: 0, scale: 0.6, rotate: 35 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            >
              <Icon />
            </motion.span>
          </AnimatePresence>

          <AnimatePresence mode="wait">
            <motion.span
              key={`${state.key}-w`}
              className="hero__rotator-word"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -18 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            >
              {state.verb}
            </motion.span>
          </AnimatePresence>

          <AnimatePresence mode="wait">
            <motion.span
              key={`${state.key}-t`}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -18 }}
              transition={{ duration: 0.45, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
            >
              {tail}
            </motion.span>
          </AnimatePresence>
        </div>

        <div className="hero__cta">
          <SpecularButton
              size="lg"
              radius={999}
              tint="#131313"
              tintOpacity={1}
              baseColor="#131313"
              textColor="#ffffff"
              lineColor="#ffffff"
              intensity={1.2}
              shineSize={14}
              onClick={() => scrollTo("fase-01")}
            >
            Recorrer las 5 fases
          </SpecularButton>

          <StarBorder as="button" color="#d9531e" speed="5s" onClick={() => scrollTo("metodologia")}>
            Ver método
          </StarBorder>
        </div>

        <div className="phase-dock">
          <Dock
            items={STATES.map((s, idx) => ({
              icon: <s.Icon />,
              label: s.verb,
              className: `ph-${s.key}${idx === i ? " is-on" : ""}`,
              onClick: () => pick(idx),
            }))}
            panelHeight={76}
            baseItemSize={52}
            magnification={68}
            dockHeight={76}
            distance={150}
          />
        </div>

        <div className="hero__body">
          <div>
            <p className="hero__lead">
              Aprende del histórico comercial ya cerrado, simula miles de futuros con
              incertidumbre real y devuelve la decisión que sobrevive al peor
              escenario.
            </p>
            <Magnet padding={70} magnetStrength={5}>
              <button className="hero__explore" type="button" onClick={() => scrollTo("fase-01")}>
                <span><IconArrowDown /></span>
                Explorar
              </button>
            </Magnet>

            {summary && (
              <p className="label" style={{ marginTop: 34, display: "block" }}>
                <CountUp to={Number(summary.rows) || 0} separator="," duration={2.2} />{" "}
                registros · {summary.period_start} → {summary.period_end}
              </p>
            )}
          </div>

          <Console summary={summary} top={top} totalSims={totalSims} phase={state.key} />

          <div className="hero__loop">
            <LogoLoop
              logos={STACK.map((name) => ({
                node: <span className="label" style={{ letterSpacing: "0.08em" }}>{name}</span>,
                title: name,
              }))}
              speed={38}
              gap={44}
              logoHeight={18}
              fadeOut
              fadeOutColor="#ededed"
              scaleOnHover
              ariaLabel="Stack técnico del proyecto"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
