import BlurText from "../reactbits/BlurText";

function Corners() {
  return (
    <>
      <span className="plate__corner plate__corner--tl" aria-hidden="true" />
      <span className="plate__corner plate__corner--tr" aria-hidden="true" />
      <span className="plate__corner plate__corner--bl" aria-hidden="true" />
      <span className="plate__corner plate__corner--br" aria-hidden="true" />
    </>
  );
}

/* Cada ilustración dibuja su propio trazo al entrar. Son SVG propios,
   no iconos de librería estirados. */

function ArtUncertainty() {
  return (
    <svg viewBox="0 0 200 150" fill="none" stroke="currentColor">
      <path d="M10 120h180" stroke="var(--line)" />
      <path
        className="draw"
        style={{ "--len": 520 }}
        d="M14 118c22 0 30-58 46-58s22 34 40 34 24-64 42-64 26 88 44 88"
        stroke="var(--faint)"
        strokeWidth="1.2"
        strokeDasharray="4 4"
      />
      <path
        className="draw"
        style={{ "--len": 520, animationDelay: "0.35s" }}
        d="M14 118c22 0 30-40 46-40s22 24 40 24 24-48 42-48 26 64 44 64"
        stroke="var(--accent)"
        strokeWidth="1.8"
      />
      <circle className="pulse-node" cx="100" cy="102" r="4" fill="var(--accent)" stroke="none" />
    </svg>
  );
}

function ArtExecution() {
  return (
    <svg viewBox="0 0 200 150" fill="none" stroke="currentColor">
      <g className="orbit" style={{ transformOrigin: "100px 75px" }}>
        <circle cx="100" cy="75" r="54" stroke="var(--line)" strokeDasharray="3 6" />
        <circle cx="154" cy="75" r="5" fill="var(--accent)" stroke="none" />
      </g>
      <circle cx="100" cy="75" r="34" stroke="var(--faint)" strokeWidth="1.2" />
      <rect x="86" y="61" width="28" height="28" rx="8" fill="var(--ink)" stroke="none" />
      <path d="M94 75.5 98.5 80l8-9" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path
        className="draw"
        style={{ "--len": 200 }}
        d="M28 30h30M28 120h30M142 30h30M142 120h30"
        stroke="var(--faint)"
        strokeWidth="1.2"
      />
    </svg>
  );
}

function ArtResidual() {
  const cols = 26;
  return (
    <svg viewBox="0 0 200 150" fill="none">
      {Array.from({ length: cols }, (_, i) => {
        const x = (i / (cols - 1)) * 2 - 1;
        const h = Math.exp(-(x * x) / 0.2) * 96 + 6;
        const hot = Math.abs(x) < 0.22;
        return (
          <rect
            key={i}
            x={10 + i * 7}
            y={126 - h}
            width="4.5"
            height={h}
            rx="2"
            fill={hot ? "var(--accent)" : "#cfcfcf"}
            style={{ transformOrigin: `0 126px`, animation: `bar-grow 1s var(--ease) ${i * 0.03}s both` }}
          />
        );
      })}
      <path d="M10 126h180" stroke="var(--line)" />
    </svg>
  );
}

function ArtRanking() {
  const rows = [
    { w: 152, label: true },
    { w: 118 },
    { w: 86 },
    { w: 58 },
  ];
  return (
    <svg viewBox="0 0 200 150" fill="none">
      {rows.map((r, i) => (
        <g key={i}>
          <rect
            x="18"
            y={28 + i * 26}
            width={r.w}
            height="12"
            rx="6"
            fill={r.label ? "var(--accent)" : "#cfcfcf"}
            style={{ transformOrigin: "18px 0", animation: `plate-slide .8s var(--ease) ${i * 0.12}s both` }}
          />
          <circle cx="10" cy={34 + i * 26} r="2.5" fill="var(--faint)" />
        </g>
      ))}
      <path d="M18 132h164" stroke="var(--line)" strokeDasharray="3 5" />
      <style>{`@keyframes plate-slide { from { transform: scaleX(0); opacity: 0 } }`}</style>
    </svg>
  );
}

const PLATES = [
  {
    n: "01",
    title: "Incertidumbre en los parámetros.",
    copy: "Cada coeficiente se muestrea de una lognormal centrada en su valor puntual. Un parámetro estimado nunca es una constante: trae su propia incertidumbre y aquí se respeta.",
    Art: ArtUncertainty,
  },
  {
    n: "02",
    title: "Riesgo de ejecución.",
    copy: "Un sorteo discreto decide en cada escenario si la palanca se aplica por completo, de forma parcial o no llega a aplicarse. Recoge el riesgo de que el plan no se ejecute tal como se aprobó.",
    Art: ArtExecution,
  },
  {
    n: "03",
    title: "Ruido residual.",
    copy: "La parte del resultado que el modelo no explica se incorpora como ruido gaussiano, calibrado sobre el error observado en el entrenamiento. Sin ese término la distribución resultaría artificialmente estrecha.",
    Art: ArtResidual,
  },
  {
    n: "04",
    title: "Ranking ajustado al riesgo.",
    copy: "Las iniciativas se ordenan por esperanza matemática penalizada por la cola izquierda, no por el techo del mejor escenario. Es lo que hace que gane la aburrida.",
    Art: ArtRanking,
  },
];

export function Platform() {
  return (
    <section className="section" id="metodologia">
      <div className="shell section__inner">
        <div className="faq__grid" style={{ marginBottom: "clamp(48px, 8vw, 110px)" }}>
          <div>
            <span className="label" style={{ display: "block", marginBottom: 24 }}>Método</span>
            <h2 className="display faq__title">
              Tres ruidos<br />y un ranking.
            </h2>
          </div>
          <p className="echo" style={{ margin: 0 }}>
            <BlurText
              text="Una simulación sin ruido calibrado es una hoja de cálculo con más pasos."
              animateBy="words"
              delay={60}
            />
          </p>
        </div>

        <div className="platform">
          {PLATES.map(({ n, title, copy, Art }) => (
            <article className="plate" key={n}>
              <div className="plate__art">
                <Corners />
                <Art />
              </div>
              <h3 className="plate__title">
                <i>{n}</i>
                {title}
              </h3>
              <p className="plate__copy">{copy}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
