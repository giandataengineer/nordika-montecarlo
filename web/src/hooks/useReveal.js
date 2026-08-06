import { useEffect, useRef, useState } from "react";

/** Revela un bloque cuando entra en viewport. El contenido es visible por
 *  defecto y solo se anima si el navegador soporta IntersectionObserver:
 *  nunca se queda en blanco si el observer no dispara. */
export function useReveal({ threshold = 0.2 } = {}) {
  const ref = useRef(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return { ref, shown };
}
