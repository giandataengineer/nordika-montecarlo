import { useEffect, useRef } from "react";
import BlurText from "../reactbits/BlurText";
import { MarcaFase } from "./MarcaFase";
import CursorGrid from "../reactbits/CursorGrid";

/* Frase fantasma que se desplaza a distinta velocidad que el resto:
   es el parallax de texto que legend usa entre secciones. */
function Echo({ text }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;

    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const r = el.getBoundingClientRect();
        const progress = 1 - r.top / window.innerHeight;
        el.style.transform = `translate3d(0, ${(-progress * 56).toFixed(1)}px, 0)`;
      });
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <p className="echo" ref={ref}>
      <span className="echo__arrow" aria-hidden="true">&rarr;</span>
      {text}
    </p>
  );
}

export function Feature({ id, index, eyebrow, faseTitulo, dark, solid, ghost, echo, copy, media, wide }) {
  return (
    <section className={dark ? "section section--dark" : "section"} id={id}>
      {/* en las bandas oscuras la rejilla se ilumina al pasar el cursor */}
      {dark && (
        <div className="section__cursor" aria-hidden="true">
          <CursorGrid cellSize={64} color="#d9531e" radius={190} lineWidth={1} maxOpacity={0.5} clickPulse />
        </div>
      )}

      <div className="shell section__inner">
        <div className={wide ? "feature feature--wide" : "feature"}>
          <div className="feature__head">
            <MarcaFase eyebrow={eyebrow ?? String(index).padStart(2, "0")} title={faseTitulo} />
            <h2 className="display split-heading">
              <span className="split-heading__solid">
                <BlurText text={solid} animateBy="words" delay={90} />
              </span>
              <span className="split-heading__ghost">{ghost}</span>
            </h2>
            <p className="feature__copy">{copy}</p>
          </div>

          <div className="feature__aside">
            {echo && <Echo text={echo} />}
            {media}
          </div>
        </div>
      </div>
    </section>
  );
}
