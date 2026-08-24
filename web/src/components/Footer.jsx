import ParticleText from "../reactbits/ParticleText";
import { IconMontecarlo } from "./Icons";

export function Footer({ meta, fases = [] }) {
  return (
    <footer className="site-footer">
      {/* La marca y el resplandor son el fondo del pie, no un bloque aparte
          debajo: así la página termina exactamente donde acaban los enlaces. */}
      <div className="site-footer__fondo" aria-hidden="true">
        <span className="site-footer__glow" />
        <div className="site-footer__wordmark">
          <ParticleText
            text="MONTECARLO"
            particleSize={1.5}
            density={5}
            color="#332f2d"
            highlightColor="#8a3f18"
            scatter={200}
            gatherDuration={1600}
            stagger={420}
            repelRadius={150}
            trigger="view"
            fontSize="clamp(3rem, 13vw, 12rem)"
            fontWeight={600}
            glow
          />
        </div>
      </div>

      <div className="shell site-footer__contenido">
        <div className="site-footer__links">
          <div>
            <h4>Recorrido</h4>
            <ul>
              {fases.map((f) => (
                <li key={f.key}>
                  <a href={`#${f.id}`}>{f.eyebrow} · {f.title}</a>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h4>Método</h4>
            <ul>
              <li><a href="#metodologia">Los tres ruidos</a></li>
              <li><a href="#faq">Preguntas frecuentes</a></li>
            </ul>
          </div>
          <div>
            <h4>Modelos</h4>
            <ul>
              <li>LogisticRegression · probabilidad de conversión</li>
              <li>HistGradientBoosting · ticket esperado</li>
              <li>Uplift contrafactual · corte temporal</li>
              <li>Monte Carlo · 10.000 escenarios</li>
            </ul>
          </div>
          <div>
            <h4>Stack</h4>
            <ul>
              <li>Python · pandas · NumPy · scikit-learn</li>
              <li>http.server · React 19 · Vite 6 · Recharts</li>
              <li>6 proveedores LLM · 57 modelos verificados</li>
            </ul>
          </div>
        </div>

        <div className="site-footer__meta">
          <span className="site-footer__firma">
            <span className="site-footer__disco">
              <IconMontecarlo />
            </span>
            Simulación Monte Carlo aplicada a decisiones de negocio
          </span>
          <span>{meta}</span>
        </div>
      </div>
    </footer>
  );
}
