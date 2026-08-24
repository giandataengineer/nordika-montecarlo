import { useCallback, useEffect, useRef, useState } from "react";
import { simular } from "../lib/montecarlo";

/* Estado unico de la simulacion para toda la pagina.

   Tres estados reales:

     espera    -> aun no se ha lanzado: no se enseña ningun resultado
     corriendo -> llegan resultados parciales y las graficas se mueven
     lista     -> los 10.000 escenarios estan hechos

   La simulacion corre en el navegador. Los modelos de ML se entrenan en
   Python y exportan el valor esperado de cada oportunidad a motor.json; aqui solo
   quedan el remuestreo y los tres ruidos, que tardan menos de un segundo.

   Antes esto sondeaba un backend cada 400 ms. Funcionaba en local, pero
   desplegado significaba cold start, rate limit y 40 segundos de espera. */
export function useSimulacion(total = 10000) {
  const [estado, setEstado] = useState("espera");
  const [motor, setMotor] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [hecho, setHecho] = useState(0);
  const [historial, setHistorial] = useState([]);
  const cancelar = useRef(null);

  useEffect(() => {
    let vivo = true;
    fetch("motor.json")
      .then((r) => r.json())
      .then((m) => vivo && setMotor(m))
      .catch(() => {});
    return () => {
      vivo = false;
      if (cancelar.current) cancelar.current();
    };
  }, []);

  const lanzar = useCallback(() => {
    if (!motor || estado === "corriendo") return;
    if (cancelar.current) cancelar.current();

    setHistorial([]);
    setHecho(0);
    setEstado("corriendo");

    cancelar.current = simular(motor, {
      total,
      // lotes pequeños al principio para que se vea arrancar, y mas grandes
      // despues: si no, los 10.000 pasan tan rapido que no se aprecia nada
      lote: 400,
      alAvanzar: (parcial, n) => {
        setRanking(parcial);
        setHecho(n);
        setHistorial((h) => {
          const punto = { iter: n };
          parcial.forEach((d) => {
            punto[d.decision] = d.expected_profit_usd;
          });
          return [...h, punto].slice(-90);
        });
      },
      alTerminar: (final) => {
        setRanking(final);
        setHecho(total);
        setEstado("lista");
      },
    });
  }, [motor, estado, total]);

  const progreso = estado === "lista" ? 100 : (hecho / total) * 100;

  const mensaje =
    estado === "corriendo"
      ? `Escenario ${hecho.toLocaleString("es-ES")} de ${total.toLocaleString("es-ES")}`
      : estado === "lista"
        ? `${total.toLocaleString("es-ES")} escenarios evaluados`
        : motor
          ? "Listo para simular"
          : "Cargando el motor";

  return {
    estado,
    corriendo: estado === "corriendo",
    lista: estado === "lista",
    listoParaLanzar: motor !== null,
    progreso,
    mensaje,
    iteracion: hecho,
    total,
    historial,
    leaderboard: ranking,
    recientes: [],
    lider: ranking[0] ?? null,
    lanzar,
  };
}
