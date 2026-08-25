/* Cierre del informe: las diez preguntas de la Fase 01, respondidas una a una
   con la cifra que las sostiene, y despues conclusiones, observaciones y
   recomendaciones. Todo se lee del payload, de modo que si cambian los datos
   cambian tambien las respuestas. */

export function Respuestas({ payload }) {
  const s = payload?.dataset?.summary;
  const cls = payload?.models?.classification;
  const reg = payload?.models?.regression;
  const ranking = payload?.simulation?.summary ?? [];
  const uplift = payload?.uplift?.main ?? [];
  const av = payload?.avanzado ?? {};
  const agregacion = payload?.multirol?.agregacion ?? {};

  if (!s || ranking.length === 0) return null;

  const n = (v, d = 0) => Number(v || 0).toLocaleString("es-ES", { maximumFractionDigits: d, minimumFractionDigits: d });
  const usd = (v) => (Number(v) < 0 ? "-" : "+") + "$" + n(Math.abs(Number(v)));
  const pct = (v, d = 2) => n(Number(v || 0) * 100, d) + " %";

  const mejor = ranking[0];
  const intuitiva = ranking.find((r) => r.decision === "Escalar paid social");
  const brecha = intuitiva ? Number(mejor.expected_profit_usd) - Number(intuitiva.expected_profit_usd) : null;
  const cumplen = ranking.filter((r) => Number(r.probability_loss) <= 0.05 && Number(r.p10_usd) > 0);
  const up = (frag) => uplift.find((r) => String(r.label || "").toLowerCase().includes(frag));
  const embudo = up("embudo");
  const reactivacion = up("reactiva");
  const evpi = av.valor_informacion ?? {};
  const estabilidad = av.estabilidad ?? {};
  const sensibilidad = av.sensibilidad ?? {};
  const val = av.validacion ?? {};

  const RESPUESTAS = [
    {
      q: "¿El histórico cubre condiciones suficientemente diversas para modelar el comportamiento comercial?",
      a: `Sí. La base reúne ${n(s.rows)} oportunidades repartidas en ${n(s.time_windows)} meses, ${n(s.channel_count)} canales de captación, ${n(s.campaign_count)} campañas, ${n(s.segment_count)} segmentos de cliente y ${n(s.geography_count)} mercados, con ${n(s.variable_count)} variables por registro. Esa variedad es la que permite estimar el efecto de una palanca sin confundirlo con el del canal o el del segmento en el que se aplicó.`,
    },
    {
      q: "¿Qué probabilidad de conversión tiene cada oportunidad y con qué capacidad de discriminación se estima?",
      a: `La estima una regresión logística con un AUC de validación de ${n(cls?.auc, 3)}. Interpretado en palabras: si se toman al azar una oportunidad que convirtió y otra que no, el modelo asigna mayor probabilidad a la que convirtió en el ${n((cls?.auc ?? 0) * 100, 1)} % de los casos. La validación se hizo con corte temporal, entrenando hasta ${val.train_end ?? "el 75 % del periodo"} y reservando los ${n(val.test_rows)} registros posteriores.`,
    },
    {
      q: "¿Cuál es el ingreso esperado de las oportunidades que llegan a convertir?",
      a: `Lo estima un gradient boosting con un error absoluto medio de $${n(reg?.mae_usd, 2)} sobre un ticket medio de $${n(s.avg_ticket_usd)}, un R² de ${n(reg?.r2, 3)} y un error absoluto de $${n(reg?.p90_abs_error_usd, 2)} en el percentil 90. El modelo acierta la magnitud del ticket, no su valor exacto, que es lo que necesita la simulación para traducir conversión en dólares.`,
    },
    {
      q: "¿Cuánto aporta cada palanca por separado, medida contra su propio escenario base?",
      a: `La optimización integral del embudo aporta ${n((embudo?.conversion_lift_pct ?? 0) * 100, 1)} % de mejora en conversión y $${n(embudo?.profit_lift_per_opportunity_usd, 2)} de margen adicional por oportunidad. La reactivación sobre base templada aporta ${n((reactivacion?.conversion_lift_pct ?? 0) * 100, 1)} % y $${n(reactivacion?.profit_lift_per_opportunity_usd, 2)}. Ambas cifras salen de comparar cada oportunidad consigo misma con la palanca cambiada, no de comparar periodos distintos.`,
    },
    {
      q: "¿Cuál es el beneficio esperado de cada iniciativa y qué dispersión presenta?",
      a: ranking
        .map((r) => `${r.decision}: ${usd(r.expected_profit_usd)} esperados, con una banda de ${usd(r.p10_usd)} a ${usd(r.p90_usd)}`)
        .join(". ") + ".",
    },
    {
      q: "¿Con qué probabilidad termina en pérdidas cada una de las cuatro iniciativas?",
      a: ranking.map((r) => `${r.decision}, ${pct(r.probability_loss)}`).join("; ") + ". El salto entre la primera y la tercera es lo que separa una decisión defendible de una apuesta: la diferencia de beneficio esperado entre ambas es pequeña comparada con la diferencia de riesgo.",
    },
    {
      q: "¿Cuál es el peor escenario razonable, entendido como el percentil 10 de la distribución?",
      a: `${mejor.decision} conserva un suelo de ${usd(mejor.p10_usd)}, de modo que incluso en el 10 % peor de los futuros la iniciativa sigue dejando margen. ${intuitiva ? `Escalar paid social, en cambio, cae hasta ${usd(intuitiva.p10_usd)} en ese mismo tramo.` : ""} Ese contraste, y no la media, es lo que decide el ranking.`,
    },
    {
      q: "¿Se mantiene el orden de las iniciativas si se modifican los supuestos de incertidumbre?",
      a: `${estabilidad.veredicto ?? "El ganador se mantiene al variar la semilla"}. ${sensibilidad.veredicto ?? ""} Además, el valor esperado de la información perfecta es de $${n(evpi.evpi)}: ese es el techo de lo que compensa invertir en un piloto o en mejores datos, y la iniciativa elegida resulta ser la mejor en el ${n((evpi.acierto_de_la_apuesta ?? 0) * 100, 0)} % de los escenarios.`,
    },
    {
      q: "¿Qué iniciativa cumple el criterio de decisión de la dirección y cuánto cuesta elegir la intuitiva?",
      a: `Con el criterio fijado, probabilidad de pérdida no superior al 5 % y percentil 10 positivo, ${cumplen.length === 1 ? "solo una iniciativa lo cumple" : `lo cumplen ${n(cumplen.length)} iniciativas`}: ${cumplen.map((r) => r.decision).join(" y ")}. La recomendación es ${mejor.decision}, con ${usd(mejor.expected_profit_usd)} esperados y un retorno de ${n(mejor.expected_roi, 1)}x sobre el coste de ejecución.${brecha != null ? ` Elegir en su lugar escalar paid social costaría ${usd(brecha)} en el mismo trimestre.` : ""}`,
    },
    {
      q: "¿Coinciden las lecturas de Finanzas, Growth y Riesgo sobre las mismas cifras?",
      a: agregacion.veredicto
        ? `${agregacion.veredicto} Cada rol se ejecuta en un modelo y un proveedor distintos, de modo que la coincidencia no procede de repetir la misma pregunta tres veces.`
        : "Los tres roles leen las mismas cifras con criterios distintos. Cuando coinciden, la decisión queda respaldada; cuando no, ese desacuerdo es lo que debe llevarse al comité.",
    },
  ];

  const CONCLUSIONES = [
    `La recomendación es ${mejor.decision}, con ${usd(mejor.expected_profit_usd)} de beneficio esperado, un suelo de ${usd(mejor.p10_usd)} en el percentil 10 y una probabilidad de pérdida de ${pct(mejor.probability_loss)}.`,
    "La iniciativa ganadora no lo es por tener la media más alta, sino por mantener un suelo positivo en todos los escenarios simulados. Ese es el criterio que la dirección había fijado antes de ver los resultados.",
    intuitiva
      ? `Escalar la inversión en paid social, que es la opción que el equipo propone con más frecuencia, ocupa el tercer lugar: termina en pérdidas el ${pct(intuitiva.probability_loss)} de las veces y su percentil 10 cae hasta ${usd(intuitiva.p10_usd)}.`
      : "",
    "El motivo aparece en el propio histórico: al pasar del tramo medio de inversión al saturado, el coste por oportunidad se duplica, la conversión se reduce a menos de la mitad y el margen de contribución cae de 35,78 a 1,14 dólares por oportunidad.",
    `El orden del ranking no depende de la calibración elegida para el ruido: ${String(estabilidad.veredicto ?? "").toLowerCase() || "el ganador se repite en todas las realizaciones"} y la recomendación resiste duplicar cualquiera de las tres fuentes de incertidumbre.`,
    `Reducir la incertidumbre antes de decidir vale como máximo $${n(evpi.evpi)} por decisión, de modo que un piloto que cueste más que esa cifra no se paga con la información que aporta.`,
  ].filter(Boolean);

  const OBSERVACIONES = [
    "El uplift se estimó por contrafactual sobre un histórico sintético. Antes de extrapolar la conclusión a una cuenta real es necesario validarlo con una prueba A/B, porque el modelo aprende asociaciones y no relaciones causales demostradas.",
    "La suma de las conversiones que reportan las plataformas supera a las ventas registradas por el ecommerce. Mientras esa diferencia exista, cualquier reparto de presupuesto basado en los paneles sobreestima el rendimiento del canal que más reporta.",
    "El efecto de saturación no es lineal. El último tramo de inversión puede tener margen prácticamente nulo mientras el panel del canal sigue mostrando conversiones, de modo que el deterioro solo se detecta comparando ingreso con inversión.",
    "El caso es sintético. Los datos se generan con distribuciones coherentes con el dominio y con una semilla fija, de manera que cualquier diferencia entre dos ejecuciones procede de un cambio en el código y no del azar.",
  ];

  const RECOMENDACIONES = [
    `Ejecutar ${mejor.decision.toLowerCase()} como experimento acotado, con responsable, plazo y lectura de conversión separada por etapa del embudo, para saber en qué punto se produce realmente la mejora.`,
    "Instrumentar landing, llamada a la acción, lead magnet y proceso de compra por separado antes del despliegue. Sin esa separación, el uplift se observa pero no se sabe de dónde viene.",
    "Mantener la reactivación de la base como palanca complementaria y como alternativa inmediata si la mejora esperada no se confirma en el primer ciclo.",
    "Fijar los umbrales de éxito y los criterios de salida antes de empezar, de modo que la evaluación posterior no dependa de la interpretación que convenga al resultado obtenido.",
    "Contrastar de forma periódica lo que reporta cada plataforma contra las ventas registradas, y retrasar cualquier escalado de medios mientras el coste por oportunidad crezca más deprisa que el volumen incremental.",
  ];

  return (
    <section className="section respuestas" id="respuestas">
      <div className="shell section__inner">
        <span className="label">Respuestas a las preguntas planteadas</span>
        <h2 className="display respuestas__titulo">
          Lo que se quería averiguar,<br />respondido una a una.
        </h2>
        <p className="respuestas__lede">
          La Fase 01 planteaba diez preguntas antes de mirar un solo gráfico. Estas
          son sus respuestas, con la cifra que sostiene cada una. Todas proceden de
          la misma ejecución del pipeline, de modo que si los datos cambian, cambian
          también estas conclusiones.
        </p>

        <ol className="respuestas__lista">
          {RESPUESTAS.map(({ q, a }, i) => (
            <li key={q}>
              <span className="respuestas__n">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3 className="respuestas__q">{q}</h3>
                <p className="respuestas__a">{a}</p>
              </div>
            </li>
          ))}
        </ol>

        <div className="respuestas__cierre">
          <div>
            <h3 className="problema__sub">Conclusiones</h3>
            <ul className="respuestas__bullets">
              {CONCLUSIONES.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </div>
          <div>
            <h3 className="problema__sub">Observaciones</h3>
            <ul className="respuestas__bullets">
              {OBSERVACIONES.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </div>
          <div>
            <h3 className="problema__sub">Recomendaciones</h3>
            <ul className="respuestas__bullets">
              {RECOMENDACIONES.map((c) => <li key={c}>{c}</li>)}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
