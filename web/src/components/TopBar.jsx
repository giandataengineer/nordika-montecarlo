import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconArrowRight, IconMontecarlo } from "./Icons";

export function TopBar({ stats, error, fases = [] }) {
  const [rotando, setRotando] = useState(0);
  const [activa, setActiva] = useState(null);
  const [arriba, setArriba] = useState(true);

  /* Dos comportamientos, no uno:
     - arriba del todo la pastilla rota por las fases, a modo de índice
     - en cuanto haces scroll deja de rotar y pasa a indicar en qué fase estás
     Congelarla en la última que tocó, que es lo que hacía antes, no informa
     de nada. */
  useEffect(() => {
    if (fases.length === 0) return undefined;

    let frame = 0;
    const medir = () => {
      frame = 0;
      const y = window.scrollY;
      setArriba(y < 80);

      // la fase activa es la última cuyo inicio ya quedó por encima del tercio
      // superior de la ventana
      const corte = y + window.innerHeight * 0.35;
      let actual = fases[0];
      for (const f of fases) {
        const el = document.getElementById(f.id);
        if (el && el.getBoundingClientRect().top + y <= corte) actual = f;
      }
      setActiva(actual);
    };

    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(medir);
    };

    medir();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [fases]);

  useEffect(() => {
    if (!arriba || fases.length === 0) return undefined;
    const id = setInterval(() => setRotando((n) => (n + 1) % fases.length), 3200);
    return () => clearInterval(id);
  }, [arriba, fases.length]);

  const fase = arriba ? fases[rotando % Math.max(fases.length, 1)] : activa;

  return (
    <header className="topbar">
      <a className="topbar__mark" href="#top">
        <span className="topbar__glyph">
          <IconMontecarlo />
        </span>
        Nordika
      </a>

      <div className="topbar__pill">
        <span className="status-dot" aria-hidden="true" />
        <span className="topbar__stats">{error ? `No se pudo cargar el motor de simulación (${error})` : stats}</span>
        {fase && (
          <AnimatePresence mode="wait">
            <motion.a
              key={fase.id + (arriba ? "-rota" : "-activa")}
              href={`#${fase.id}`}
              className={arriba ? "" : "is-activa"}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            >
              {!arriba && <i className="topbar__aqui" aria-hidden="true" />}
              {fase.eyebrow} · {fase.title}
              {arriba && (
                <IconArrowRight style={{ width: 12, height: 12, verticalAlign: "-1px", marginLeft: 6 }} />
              )}
            </motion.a>
          </AnimatePresence>
        )}
      </div>

      {/* Sin botón de menú: no abría nada. La navegación real está en el pie,
          y la pastilla central ya enlaza a cada fase. */}
      <span className="topbar__right" aria-hidden="true" />
    </header>
  );
}
