/* Monte Carlo en el navegador.

   Los modelos de ML se entrenan en Python y exportan el valor esperado de cada
   oportunidad bajo cada estrategia. Lo que queda aquí es el remuestreo bootstrap y
   los tres ruidos, que es aritmetica: 10.000 iteraciones tardan menos de un
   segundo y no necesitan servidor.

   La logica replica scripts/simulacion_montecarlo.py:simulate_decisions. */

// Generador con semilla para que la pagina de el mismo resultado en cada
// visita. Sin esto, dos personas viendo el proyecto verían números distintos.
function mulberry32(semilla) {
  let a = semilla >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Box-Muller: dos uniformes dan una normal estandar.
function normal(rand) {
  let u = 0;
  let v = 0;
  while (u === 0) u = rand();
  while (v === 0) v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

function lognormal(rand, mu, sigma) {
  return Math.exp(mu + sigma * normal(rand));
}

// Sorteo discreto con pesos, para el riesgo de no ser convocado.
function discreta(rand, valores, pesos) {
  const total = pesos.reduce((a, b) => a + b, 0);
  let r = rand() * total;
  for (let i = 0; i < valores.length; i += 1) {
    r -= pesos[i];
    if (r <= 0) return valores[i];
  }
  return valores[valores.length - 1];
}

function percentil(ordenados, q) {
  const pos = (ordenados.length - 1) * q;
  const bajo = Math.floor(pos);
  const alto = Math.ceil(pos);
  if (bajo === alto) return ordenados[bajo];
  return ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (pos - bajo);
}

/* Corre la simulación completa.

   Se ejecuta por lotes con setTimeout para no bloquear el hilo principal: si
   no, la interfaz se congela los 10.000 escenarios y no se ve nada moverse.

   La pausa entre lotes no es un adorno. El navegador termina los 10.000
   escenarios en menos de un segundo, así que sin ritmo el anillo saltaba de 0
   a 100 y las curvas aparecían ya dibujadas: la fase prometía una simulación
   en vivo y enseñaba un resultado congelado. `duracionMs` reparte el trabajo
   en `pasos` tramos para que el avance se vea escenario a escenario. */
export function simular(
  motor,
  { total = 10000, pasos = 130, duracionMs = 26000, alAvanzar, alTerminar } = {},
) {
  const rand = mulberry32(motor.semilla);
  const base = motor.valor_base;
  const nombres = Object.keys(motor.estrategias);

  const acumulado = {};
  nombres.forEach((n) => {
    acumulado[n] = [];
  });

  const lote = Math.max(1, Math.ceil(total / pasos));
  const pausa = Math.max(0, Math.round(duracionMs / pasos));

  let hecho = 0;
  let cancelado = false;
  let ultimoPintado = 0;

  function siguienteLote() {
    if (cancelado) return;
    const hasta = Math.min(hecho + lote, total);

    for (let s = hecho; s < hasta; s += 1) {
      // mismos indices para todas las estrategias en cada escenario: se
      // comparan sobre la misma realización, no sobre muestras distintas
      const idx = new Array(base.length);
      for (let i = 0; i < base.length; i += 1) idx[i] = Math.floor(rand() * base.length);

      for (const nombre of nombres) {
        const e = motor.estrategias[nombre];
        let delta = 0;

        if (e.mismo_tamano) {
          for (let i = 0; i < idx.length; i += 1) delta += e.valor[idx[i]] - base[idx[i]];
        } else {
          // la estrategia anade oportunidades nuevas: solo cuentan esas
          const extra = e.valor.length - base.length;
          for (let i = 0; i < extra; i += 1) {
            delta += e.valor[base.length + Math.floor(rand() * extra)];
          }
        }

        const [mu, sigma] = e.ruido.incertidumbre;
        const [valores, pesos] = e.ruido.ejecucion;
        const [suelo, proporcion] = e.ruido.residual;

        const incertidumbre = lognormal(rand, mu, sigma);
        const ejecucion = discreta(rand, valores, pesos);
        const residual = normal(rand) * (suelo + Math.abs(delta) * proporcion);

        acumulado[nombre].push(delta * incertidumbre * ejecucion + residual - e.coste_fijo);
      }
    }

    hecho = hasta;

    // resumir implica ordenar 10.000 valores por estrategia: hacerlo en cada
    // lote y repintar las graficas cada vez atasca el hilo principal
    const ahora = performance.now();
    if (alAvanzar && (ahora - ultimoPintado > 40 || hecho >= total)) {
      ultimoPintado = ahora;
      alAvanzar(resumen(acumulado, motor), hecho, total);
    }

    if (hecho < total) {
      setTimeout(siguienteLote, pausa);
    } else if (alTerminar) {
      alTerminar(resumen(acumulado, motor), acumulado);
    }
  }

  setTimeout(siguienteLote, pausa);
  return () => {
    cancelado = true;
  };
}

function resumen(acumulado, motor) {
  return Object.entries(acumulado)
    .map(([decision, valores]) => {
      const orden = [...valores].sort((a, b) => a - b);
      const media = valores.reduce((a, b) => a + b, 0) / valores.length;
      const inversion = motor.estrategias[decision].coste_fijo;
      return {
        decision,
        expected_profit_usd: media,
        p10_usd: percentil(orden, 0.1),
        p50_usd: percentil(orden, 0.5),
        p90_usd: percentil(orden, 0.9),
        probability_loss: valores.filter((v) => v < 0).length / valores.length,
        expected_roi: media / inversion,
      };
    })
    .sort((a, b) => b.expected_profit_usd - a.expected_profit_usd)
    .map((fila, i) => ({ ...fila, ranking: i + 1 }));
}
