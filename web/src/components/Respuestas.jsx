/* Cierre. Versión corta: la decisión, por que gana, que costaria equivocarse y
   que la invalidaria. Antes eran diez preguntas respondidas una a una, unas 900
   palabras. Quien revisa el proyecto ya vio el ranking y la distribución dos
   secciones antes; repetirlo en prosa no aportaba nada. */

export function Respuestas({ payload }) {
  const ranking = payload?.simulation?.summary ?? [];
  const av = payload?.avanzado ?? {};
  const agregacion = payload?.multirol?.agregacion ?? {};

  if (ranking.length === 0) return null;

  const n = (v, d = 0) => Number(v || 0).toLocaleString("es-ES", { maximumFractionDigits: d, useGrouping: "always" });
  const usd = (v) => (Number(v) < 0 ? "-" : "+") + "$" + n(Math.abs(Number(v)));
  const pct = (v, d = 1) => n(Number(v || 0) * 100, d) + " %";

  const mejor = ranking[0];
  const intuitiva = ranking.find((r) => r.decision === "Escalar paid social");
  const brecha = intuitiva ? Number(mejor.expected_profit_usd) - Number(intuitiva.expected_profit_usd) : null;
  const evpi = av.valor_informacion ?? {};
  const estabilidad = av.estabilidad ?? {};

  const CLAVES = [
    {
      k: "Decisión",
      v: mejor.decision,
      d: `${usd(mejor.expected_profit_usd)} esperados · ${n(mejor.expected_roi, 1)}x de retorno · ${pct(mejor.probability_loss, 2)} de probabilidad de pérdida`,
    },
    {
      k: "Por qué gana",
      v: `Suelo de ${usd(mejor.p10_usd)}`,
      d: "Gana por el suelo. Su percentil 10 sigue en positivo, mientras que la segunda tiene mejor techo y peor suelo.",
    },
    {
      k: "Coste de equivocarse",
      v: brecha != null ? usd(brecha) : "—",
      d: intuitiva
        ? `Escalar paid social pierde dinero el ${pct(intuitiva.probability_loss)} de las veces y su percentil 10 cae a ${usd(intuitiva.p10_usd)}.`
        : "",
    },
    {
      k: "Cuánto vale más información",
      v: `$${n(evpi.evpi)}`,
      d: `Es el techo de lo que compensa gastar en un piloto. La apuesta elegida es la mejor en el ${n((evpi.acierto_de_la_apuesta ?? 0) * 100, 0)} % de los escenarios.`,
    },
  ];

  const SALVEDADES = [
    `${estabilidad.veredicto ?? "El ganador se repite al variar la semilla"}, y la recomendación aguanta duplicar cualquiera de los tres ruidos.`,
    agregacion.veredicto ?? "Los tres roles de negocio leen las mismas cifras con criterios distintos.",
    "El uplift se estimó por contrafactual sobre un histórico sintético. Antes de extrapolarlo a una cuenta real hay que validarlo con un A/B.",
  ];

  return (
    <section className="section respuestas" id="respuestas">
      <div className="shell section__inner">
        <span className="label">La decisión</span>
        <h2 className="display respuestas__titulo">
          Qué hacer con el<br />presupuesto del trimestre.
        </h2>

        <div className="respuestas__claves">
          {CLAVES.map(({ k, v, d }) => (
            <article key={k}>
              <span className="label">{k}</span>
              <strong>{v}</strong>
              <p>{d}</p>
            </article>
          ))}
        </div>

        <ul className="respuestas__bullets respuestas__salvedades">
          {SALVEDADES.map((s) => <li key={s}>{s}</li>)}
        </ul>
      </div>
    </section>
  );
}
