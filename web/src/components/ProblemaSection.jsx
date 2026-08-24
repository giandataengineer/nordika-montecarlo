import { MarcaFase } from "./MarcaFase";
import { IconAlert, IconLayers, IconSimulate } from "./Icons";

/* Fase 01. Antes la pagina abria con graficas: se veia el metodo pero no el
   problema, y sin problema las graficas son adorno.
   El registro es deliberado: segunda persona, cifras concretas y la jerga
   traducida. */

const CANDIDATAS = [
  {
    tipo: "La que elegirías",
    nombre: "Escalar paid social",
    inversion: "$9.000",
    tono: "riesgo",
    copy: "Subir el presupuesto en Meta y TikTok. Es lo que pide el equipo, lo que muestran bien los paneles y lo que cualquiera propondría en una reunión de crecimiento. Trae más volumen desde el primer día.",
  },
  {
    tipo: "La aburrida",
    nombre: "Optimizar la conversión del sitio",
    inversion: "$1.200",
    tono: "calma",
    copy: "Landing, CTA, lead magnet y checkout. No compra ni un clic más: mejora lo que ya llega. Nadie la propone en una reunión porque no suena a nada y no sale en ningún panel.",
  },
  {
    tipo: "La segura",
    nombre: "Reactivación y remarketing",
    inversion: "$2.500",
    tono: "calma",
    copy: "Trabajar la base que ya interactuó contigo. Coste incremental bajo y ticket alto, porque son gente que ya te conoce. El techo lo pone el tamaño de esa base, y no crece sola.",
  },
  {
    tipo: "La que hace ruido",
    nombre: "Abrir categoría nueva",
    inversion: "$12.000",
    tono: "riesgo",
    copy: "Ticket mayor y mercado sin explotar. Es la del techo más alto y la única donde el dinero se gasta antes de saber si funciona: catálogo, fotos, stock y campañas de lanzamiento.",
  },
];

const RAZONES = [
  {
    n: "01",
    Icon: IconLayers,
    titulo: "Tu histórico te dice lo que pasó. Nunca lo que habría pasado.",
    copy: "En tus datos está la campaña que lanzaste. No está la fila que diga cuánto habrías vendido ese martes con otra landing, porque esa versión no existió. Comparar iniciativas con el histórico crudo es comparar cosas que nunca coincidieron en el tiempo.",
    respuesta: "Por eso el sistema no compara periodos: coge la misma oportunidad y le cambia una sola palanca.",
    capa: "Capa 1 · uplift contrafactual",
  },
  {
    n: "02",
    Icon: IconSimulate,
    titulo: "Un número esconde el riesgo. Una distribución lo enseña.",
    copy: "El retorno de una campaña no es un valor, es un rango. La ejecución se retrasa, la competencia puja el mismo inventario, el canal se satura. Una iniciativa puede tener la mejor media del grupo y aun así perder dinero uno de cada seis trimestres. Y el presupuesto se compromete una vez, no cien.",
    respuesta: "Por eso no se calcula un resultado, se calculan diez mil y se mira la forma que tienen.",
    capa: "Capa 2 · 10.000 futuros con ruido",
  },
  {
    n: "03",
    Icon: IconAlert,
    titulo: "Pregunta a tres personas cuál es la mejor y te dan tres respuestas.",
    copy: "El CEO mira el retorno sobre el capital y el payback. Growth mira qué palanca deja aprender más rápido. Riesgo mira el peor escenario y qué pasa si el canal se satura. Las tres tienen razón, y no siempre señalan la misma casilla.",
    respuesta: "Cuando los tres coinciden, la decisión está sólida. Cuando no, ese desacuerdo es justo lo que hay que llevar al comité.",
    capa: "Capa 3 · tres lecturas independientes",
  },
];

const CAPACIDADES = [
  {
    titulo: "No solo predice: interviene.",
    copy: "Un modelo normal te da un número y ahí se acaba. Este coge la misma oportunidad histórica, le cambia la landing y vuelve a preguntar. La diferencia entre las dos respuestas es lo que aporta esa palanca, aislada de todo lo demás.",
  },
  {
    titulo: "No promedia el caos: lo simula.",
    copy: "En vez de inventar un escenario malo restando un 30 %, se inyectan tres ruidos con forma propia: la incertidumbre del modelo como lognormal, el riesgo de ejecución como distribución discreta, y el error residual como gaussiano. El escenario malo ya no es un número redondo: es el percentil 10 de diez mil ejecuciones.",
  },
  {
    titulo: "No entrega un gráfico: entrega una decisión defendible.",
    copy: "Tres modelos independientes leen las mismas cifras desde CEO, Growth y Riesgo. Y un guardarraíl retira cualquier frase que contradiga los números que tiene al lado, en vez de dejarla pasar. Lo que llega al comité se puede discutir línea por línea.",
  },
];

export function ProblemaSection({ fase, summary, ranking = [] }) {
  const n = (v, d = 0) => Number(v || 0).toLocaleString("es-ES", { maximumFractionDigits: d });
  const usd = (v) => (v < 0 ? "-" : "+") + "$" + n(Math.abs(v));

  /* La cifra del error sale del ranking, no esta escrita a mano: si cambian
     los datos, cambia sola. */
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
            Cuatro formas de gastar<br />el mismo presupuesto.
          </h2>
          <p className="problema__lede">
            Imagina que llevas la captación de pago de un ecommerce. Tienes cuatro
            iniciativas sobre la mesa y presupuesto para una. No hay ensayo
            general: el trimestre pasa una sola vez.
          </p>

          {brecha != null && (
            <div className="problema__coste">
              <span className="label">Lo que cuesta elegir con el estómago</span>
              <strong className="problema__coste-cifra">{usd(brecha)}</strong>
              <p>
                Esa es la distancia entre <b>{mejor.decision}</b>, que la simulación
                deja primera con {usd(Number(mejor.expected_profit_usd))}, y{" "}
                <b>Escalar paid social</b>, que es la que elegirías tú, yo y
                cualquiera mirando los paneles. Termina en{" "}
                {usd(Number(intuitiva.expected_profit_usd))}. Mismo trimestre, mismo
                presupuesto, mismo equipo.
              </p>
            </div>
          )}
        </header>

        {/* El villano. Nombrarlo antes de presentar el metodo hace que el metodo
            se lea como respuesta y no como demo tecnica. */}
        <div className="problema__villano">
          <div>
            <span className="label">Cómo se decide esto hoy</span>
            <blockquote className="problema__cita">
              «Escenario malo, menos 30 %.<br />Escenario bueno, más 30 %.»
            </blockquote>
            <p className="problema__nota">
              ¿Y por qué 30 y no 55? Por nada. Porque es un número redondo.
            </p>
          </div>
          <div className="problema__villano-copy">
            <p>
              Y hay algo peor que el Excel. Abre el panel de Meta y te dirá que
              generó 400 ventas. Abre el de Google y dirá 350. Abre el de TikTok y
              dirá 200. Suma: 950. Mira tu ecommerce: vendiste 600.
            </p>
            <p>
              Cada plataforma se cuelga la misma venta. Y desde que iOS pide permiso
              para rastrear y los navegadores bloquean cookies de terceros, la
              confianza en la atribución entre canales <b>cayó por debajo del 50 %</b>.
              El 71 % de las marcas ya está reduciendo su dependencia de esos datos.
            </p>
            <p>
              Así que decides con tres números inventados y tres paneles que se
              contradicen. Eso no es decidir: <b>es apostar con vocabulario financiero.</b>
            </p>
          </div>
        </div>

        {/* El mecanismo del caso: la saturacion de canal. */}
        <div className="problema__activo">
          <div className="problema__activo-texto">
            <h3 className="problema__sub">
              Comprar más tráfico funciona. Hasta que deja de funcionar.
            </h3>
            <p>
              En palabras llanas: subes el presupuesto de un canal y llegan más
              visitas. Al principio salen casi igual de baratas y convierten casi
              igual de bien. El panel se pone verde y todo el mundo está contento.
            </p>
            <p>
              Pero la gente buena de ese canal es finita. Cuando la agotas, el
              algoritmo empieza a traerte a los siguientes, que son peores. Y para
              alcanzarlos hay que pujar más alto.
            </p>
            <p>
              <b>En este histórico, pasar del tramo medio al saturado casi dobla el
              coste por oportunidad y hunde la conversión a menos de la mitad.</b> El
              margen por oportunidad cae de 35 dólares a uno.
            </p>
            <p>
              Y eso el panel no te lo dice, porque sigue contando conversiones. Solo
              lo ves cuando comparas lo que ganaste con lo que gastaste, que es
              precisamente lo que la atribución rota ya no te deja hacer.
            </p>
          </div>

          <ol className="mecanismo">
            <li>
              <span className="mecanismo__paso">Tramo bajo</span>
              <b>$9,66</b>
              <span>por oportunidad, convierte al 6,4 %</span>
            </li>
            <li>
              <span className="mecanismo__paso">Tramo alto</span>
              <b>$14,35</b>
              <span>por oportunidad, convierte al 4,9 %</span>
            </li>
            <li className="mecanismo--coste">
              <span className="mecanismo__paso">Saturado</span>
              <b>$20,56</b>
              <span>por oportunidad, convierte al 2,8 %. El margen se queda en $1.</span>
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
                  <dt>Ingreso</dt>
                  <dd>{n(summary.ingreso_usd / 1000)}k <span>USD atribuidos</span></dd>
                </div>
                <div>
                  <dt>Inversión</dt>
                  <dd>{n((summary.pct_inversion_sobre_ingreso ?? 0) * 100, 1)}% <span>sobre el ingreso</span></dd>
                </div>
                <div>
                  <dt>Conversión</dt>
                  <dd>{n((summary.conversion_rate ?? 0) * 100, 1)}% <span>media del histórico</span></dd>
                </div>
                <div>
                  <dt>Canales</dt>
                  <dd>{n(summary.channel_count)} <span>vías de captación</span></dd>
                </div>
                <div>
                  <dt>Ticket</dt>
                  <dd>{n(summary.avg_ticket_usd)} <span>USD medio</span></dd>
                </div>
              </>
            )}
          </dl>
        </div>

        {/* Las cuatro candidatas, con su inversion. */}
        <div className="problema__candidatas">
          <span className="label">
            Las cuatro sobre la mesa · cada una se rompe por un sitio distinto
          </span>
          <div className="problema__grid">
            {CANDIDATAS.map((c) => (
              <article className={`candidata candidata--${c.tono}`} key={c.nombre}>
                <span className="candidata__tipo">{c.tipo}</span>
                <h4 className="candidata__nombre">{c.nombre}</h4>
                <span className="candidata__inversion">{c.inversion} de inversión</span>
                <p>{c.copy}</p>
              </article>
            ))}
          </div>
        </div>

        {/* Las tres razones. Cada una justifica una capa. */}
        <div className="problema__razones">
          <span className="label">
            Vale, ¿y por qué no basta con mirar el histórico?
          </span>
          {RAZONES.map(({ n: num, Icon, titulo, copy, respuesta, capa }) => (
            <article className="razon" key={num}>
              <span className="razon__n">{num}</span>
              <div>
                <h4 className="razon__titulo">{titulo}</h4>
                <p>{copy}</p>
                <p className="razon__respuesta">{respuesta}</p>
                <span className="razon__capa">
                  <Icon style={{ width: 14, height: 14 }} />
                  {capa}
                </span>
              </div>
            </article>
          ))}
        </div>

        {/* Que hace el sistema que un Excel no puede. */}
        <div className="problema__solucion">
          <span className="label">Y entonces, ¿qué hace este sistema que un Excel no?</span>
          <h3 className="problema__sub problema__sub--ancho">
            No queremos un modelo que prediga. Queremos uno que además intervenga,
            estrese el resultado y lo traduzca a una decisión que alguien pueda
            defender.
          </h3>
          <div className="solucion__grid">
            {CAPACIDADES.map((c) => (
              <article className="capacidad" key={c.titulo}>
                <h4>{c.titulo}</h4>
                <p>{c.copy}</p>
              </article>
            ))}
          </div>
          <p className="problema__cierre">
            El resultado no es la opción más espectacular. Es la que sigue en pie
            cuando le quitas la suerte.
          </p>
        </div>
      </div>
    </section>
  );
}
