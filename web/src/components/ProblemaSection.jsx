import { MarcaFase } from "./MarcaFase";

/* Fase 01. Version corta.
   Tenia enunciado largo, diez preguntas, tres razones y tres capacidades: unas
   1.600 palabras antes de la primera cifra. Quien revisa el proyecto quiere el
   problema, el mecanismo y el coste de equivocarse, y lo quiere en la primera
   pantalla. Lo demas vive en el README. */

const CANDIDATAS = [
  {
    tipo: "La que propone el equipo",
    nombre: "Escalar paid social",
    inversion: "$9.000",
    tono: "riesgo",
    copy: "Más presupuesto en Meta y TikTok. Trae volumen desde el primer día y es la que mejor luce en los paneles.",
  },
  {
    tipo: "La de menor coste",
    nombre: "Optimizar la conversión del sitio",
    inversion: "$1.200",
    tono: "calma",
    copy: "Landing, CTA, lead magnet y checkout. No trae visitas nuevas, aprovecha mejor las que ya entran.",
  },
  {
    tipo: "La de menor riesgo",
    nombre: "Reactivación y remarketing",
    inversion: "$2.500",
    tono: "calma",
    copy: "Trabaja la base que ya te conoce. Cuesta poco por oportunidad y el ticket es alto, pero esa base no crece sola.",
  },
  {
    tipo: "La de mayor techo",
    nombre: "Abrir categoría nueva",
    inversion: "$12.000",
    tono: "riesgo",
    copy: "Línea de producto con ticket mayor. Aquí el gasto se compromete entero antes de saber si el mercado responde.",
  },
];

export function ProblemaSection({ fase, summary, ranking = [] }) {
  const n = (v, d = 0) => Number(v || 0).toLocaleString("es-ES", { maximumFractionDigits: d });
  const usd = (v) => (v < 0 ? "-" : "+") + "$" + n(Math.abs(v));

  /* La cifra sale del ranking, no esta escrita a mano: si cambian los datos,
     cambia sola. */
  const mejor = ranking[0];
  const intuitiva = ranking.find((r) => r.decision === "Escalar paid social");
  const brecha =
    mejor && intuitiva
      ? Number(mejor.expected_profit_usd) - Number(intuitiva.expected_profit_usd)
      : null;

  return (
    <section className="section problema" id="fase-00">
      <div className="shell section__inner">
        <header className="problema__head">
          <MarcaFase eyebrow={fase?.eyebrow ?? "Fase 01"} title={fase?.title ?? "El problema"} />
          <h2 className="display problema__titulo">
            Cuatro iniciativas<br />y un solo presupuesto.
          </h2>
          <p className="problema__lede">
            La unidad de captación de pago de un ecommerce reparte el presupuesto del
            trimestre. Cuatro iniciativas encima de la mesa y dinero para una. Detrás
            hay 20.000 oportunidades cerradas en 28 meses.
          </p>

          {brecha != null && (
            <div className="problema__coste">
              <span className="label">Lo que cuesta decidir por intuición</span>
              <strong className="problema__coste-cifra">{usd(brecha)}</strong>
              <p>
                Es la diferencia entre <b>{mejor.decision}</b>, que la simulación deja
                primera con {usd(Number(mejor.expected_profit_usd))}, y{" "}
                <b>escalar paid social</b>, que termina en{" "}
                {usd(Number(intuitiva.expected_profit_usd))} pese a ser la que casi
                cualquiera elegiría mirando los paneles. Mismo trimestre, mismo
                presupuesto, mismo equipo.
              </p>
            </div>
          )}
        </header>

        <div className="problema__villano">
          <div>
            <span className="label">Por qué no sirven los paneles</span>
            <blockquote className="problema__cita">
              400 + 350 + 200<br />= 600 ventas
            </blockquote>
            <p className="problema__nota">
              Meta, Google y TikTok reportan 950 ventas entre los tres. El ecommerce
              registró 600.
            </p>
          </div>
          <div className="problema__villano-copy">
            <p>
              Cada plataforma se atribuye por completo una venta en la que
              intervinieron varias. Desde que iOS exige permiso para el rastreo y los
              navegadores bloquean cookies de terceros, la confianza en la atribución
              entre canales <b>está por debajo del 50 %</b>, y el 71 % de las marcas
              declara estar reduciendo su dependencia de esos datos.
            </p>
            <p>
              La alternativa de siempre tampoco arregla nada: tres escenarios en una
              hoja de cálculo, malo menos 30 % y bueno más 30 %, sin que nadie sepa qué
              probabilidad tiene ese 30 ni cuántas veces de cada cien se acaba perdiendo
              dinero.
            </p>
          </div>
        </div>

        <div className="problema__activo">
          <div className="problema__activo-texto">
            <h3 className="problema__sub">
              El mecanismo: la audiencia se satura antes de lo que dice el panel.
            </h3>
            <p>
              Al subir el presupuesto de un canal entra más tráfico, pero la audiencia
              con intención de compra se acaba. Cuando se agota, el algoritmo empieza a
              traer perfiles peores y hay que pujar más alto para llegar a ellos. El
              coste sube justo cuando la conversión baja.
            </p>
            <p>
              <b>Del tramo medio al saturado, el coste por oportunidad se duplica y la
              conversión cae a menos de la mitad.</b> El margen de contribución pasa de
              35,78 a 1,14 dólares. El panel del canal no lo muestra, porque sigue
              contando conversiones.
            </p>
          </div>

          <ol className="mecanismo">
            <li>
              <span className="mecanismo__paso">Tramo bajo</span>
              <b>$9,66</b>
              <span>por oportunidad · convierte 6,4 % · deja $35,44</span>
            </li>
            <li>
              <span className="mecanismo__paso">Tramo alto</span>
              <b>$14,35</b>
              <span>por oportunidad · convierte 4,9 % · deja $23,20</span>
            </li>
            <li className="mecanismo--coste">
              <span className="mecanismo__paso">Tramo saturado</span>
              <b>$20,56</b>
              <span>por oportunidad · convierte 2,8 % · deja $1,14</span>
            </li>
          </ol>

          <dl className="problema__ficha">
            {summary && (
              <>
                <div>
                  <dt>Oportunidades</dt>
                  <dd>{n(summary.rows)} <span>en 28 meses</span></dd>
                </div>
                <div>
                  <dt>Ingreso atribuido</dt>
                  <dd>${n((summary.ingreso_usd ?? 0) / 1e6, 2)} M <span>en el periodo</span></dd>
                </div>
                <div>
                  <dt>Inversión</dt>
                  <dd>{n((summary.pct_inversion_sobre_ingreso ?? 0) * 100, 1)} % <span>sobre el ingreso</span></dd>
                </div>
                <div>
                  <dt>Conversión</dt>
                  <dd>{n((summary.conversion_rate ?? 0) * 100, 1)} % <span>media histórica</span></dd>
                </div>
                <div>
                  <dt>Canales</dt>
                  <dd>{n(summary.channel_count)} <span>vías de captación</span></dd>
                </div>
                <div>
                  <dt>Ticket medio</dt>
                  <dd>${n(summary.avg_ticket_usd)} <span>por venta</span></dd>
                </div>
              </>
            )}
          </dl>
        </div>

        <div className="problema__candidatas">
          <span className="label">
            Las cuatro iniciativas · coste de ejecución entre paréntesis
          </span>
          <div className="problema__grid">
            {CANDIDATAS.map((c) => (
              <article className={`candidata candidata--${c.tono}`} key={c.nombre}>
                <span className="candidata__tipo">{c.tipo}</span>
                <h4 className="candidata__nombre">{c.nombre}</h4>
                <span className="candidata__inversion">{c.inversion} de ejecución</span>
                <p>{c.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
