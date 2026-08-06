import { useCallback, useEffect, useRef, useState } from "react";

/* Estado unico de la simulacion para toda la pagina.

   Antes cada bloque leia el payload consolidado y pintaba el resultado final
   desde el primer segundo, asi que la simulacion no cambiaba nada de lo que se
   veia. Aqui hay tres estados reales:

     espera    -> aun no se ha lanzado: no se enseña ningun resultado
     corriendo -> llegan resultados parciales del backend y las graficas se mueven
     lista     -> los 10.000 escenarios estan hechos

   Los datos parciales (`leaderboard`, `recent_runs`) vienen del propio backend,
   no de una animacion inventada en el navegador. */
export function useSimulacion(total = 10000) {
  const [estado, setEstado] = useState("espera");
  const [st, setSt] = useState(null);
  const [historial, setHistorial] = useState([]);
  const timer = useRef(null);
  const vioCorrer = useRef(false);

  const parar = useCallback(() => {
    clearInterval(timer.current);
    timer.current = null;
  }, []);

  const sondear = useCallback(async () => {
    try {
      const r = await fetch("/api/montecarlo-status").then((x) => x.json());
      setSt(r);

      if (r.running) vioCorrer.current = true;

      // el historial guarda como evoluciona cada decision a lo largo del run:
      // es lo que hace que las curvas crezcan en vez de aparecer de golpe
      if (r.leaderboard?.length) {
        setHistorial((h) => {
          const ultimo = h[h.length - 1];
          if (ultimo && ultimo.iter === r.current_simulation) return h;
          const punto = { iter: r.current_simulation || 0 };
          r.leaderboard.forEach((d) => {
            punto[d.decision] = Number(d.expected_profit_usd || 0);
          });
          return [...h, punto].slice(-90);
        });
      }

      if (r.completed || (vioCorrer.current && !r.running)) {
        setEstado("lista");
        parar();
      }
    } catch {
      parar();
      setEstado((e) => (e === "corriendo" ? "espera" : e));
    }
  }, [parar]);

  // al montar se consulta una vez: si ya hay una simulacion completa de una
  // sesion anterior, la pagina arranca directamente en "lista"
  useEffect(() => {
    let vivo = true;
    fetch("/api/montecarlo-status")
      .then((x) => x.json())
      .then((r) => {
        if (!vivo) return;
        setSt(r);
        if (r.completed || Number(r.progress_pct) >= 100) setEstado("lista");
        else if (r.running) {
          setEstado("corriendo");
          vioCorrer.current = true;
          timer.current = setInterval(sondear, 400);
        }
      })
      .catch(() => {});
    return () => {
      vivo = false;
      clearInterval(timer.current);
    };
  }, [sondear]);

  const lanzar = useCallback(async () => {
    if (estado === "corriendo") return;
    vioCorrer.current = false;
    setHistorial([]);
    setEstado("corriendo");
    parar();
    timer.current = setInterval(sondear, 400);
    await fetch("/api/montecarlo-reset", { method: "POST" }).catch(() => {});
    await fetch("/api/stage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage: "montecarlo" }),
    }).catch(() => {});
    // red de seguridad si el backend deja de responder
    setTimeout(() => {
      if (timer.current) {
        parar();
        setEstado((e) => (e === "corriendo" ? "lista" : e));
      }
    }, 180000);
  }, [estado, parar, sondear]);

  const progreso = Number(st?.progress_pct || 0);
  const iteracion = Number(st?.current_simulation || 0);

  return {
    estado,
    corriendo: estado === "corriendo",
    lista: estado === "lista",
    progreso: estado === "lista" ? 100 : progreso,
    iteracion: estado === "lista" ? total : iteracion,
    total: Number(st?.total_simulations || total),
    // durante el run manda el leaderboard parcial; al terminar, el consolidado
    leaderboard: st?.leaderboard ?? [],
    recientes: st?.recent_runs ?? [],
    historial,
    lider: st?.leader ?? null,
    mensaje: st?.status_message || "",
    lanzar,
  };
}
