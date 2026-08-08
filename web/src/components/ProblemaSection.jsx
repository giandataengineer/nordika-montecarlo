import { MarcaFase } from "./MarcaFase";
import { IconAlert, IconLayers, IconSimulate } from "./Icons";

/* Fase 01. Antes la pagina abria con graficas: se veia el metodo pero no el
   problema, y sin problema las graficas son adorno.
   El registro es deliberado: segunda persona, cifras concretas y la jerga
   traducida. Un operador de red tiene que entender esto sin abrir el codigo,
   y un revisor tecnico tiene que ver que hay criterio debajo. */

const CANDIDATAS = [
  {
    tipo: "La que elegirías",
    nombre: "Arbitraje agresivo",
    inversion: "$95.000",
    tono: "riesgo",
    copy: "Dos ciclos completos al día y descarga a fondo. Persigues cada diferencial que aparece. Es la que más energía mueve, la que más factura y la que cualquiera elegiría mirando el informe del primer mes.",
  },
  {
    tipo: "La aburrida",
    nombre: "Ventana conservadora",
    inversion: "$18.000",
    tono: "calma",
    copy: "Solo los dos mejores diferenciales del día y descarga limitada. Ganas menos por ciclo, pero la batería llega entera a fin de año. Casi nadie la propone en una reunión porque no suena a nada.",
  },
  {
    tipo: "La segura",
    nombre: "Servicios de regulación",
    inversion: "$28.000",
    tono: "calma",
    copy: "Le prometes capacidad al operador de red y te paga por tenerla reservada, la use o no. Cobras por estar quieto. El precio: esa capacidad ya no está cuando aparece el diferencial del año.",
  },
  {
    tipo: "La que hace ruido",
    nombre: "Híbrido certificado",
    inversion: "$140.000",
    tono: "riesgo",
    copy: "Entrar a un mercado nuevo. Hay que pagar controles y certificación antes de facturar un dólar. Es la del techo más alto y la única donde, si la habilitación se retrasa, ya gastaste el dinero.",
  },
];

const RAZONES = [
  {
    n: "01",
    Icon: IconLayers,
    titulo: "El histórico te dice lo que pasó. Nunca lo que habría pasado.",
    copy: "En tus datos está lo que hiciste. No está la fila que diga cuánto habrías ganado ese martes si hubieras descargado al 80 % en vez de al 50 %, porque esa operación no ocurrió. Comparar estrategias con el histórico crudo es comparar cosas que nunca coincidieron en el tiempo.",
    respuesta: "Por eso el sistema no compara periodos: coge la misma hora y le cambia una sola palanca.",
    capa: "Capa 1 · uplift contrafactual",
  },
  {
    n: "02",
    Icon: IconSimulate,
    titulo: "Un número esconde el riesgo. Una distribución lo enseña.",
    copy: "El precio de la luz tiene cola gruesa: casi todas las horas son planas y unas pocas se disparan. Con esa forma, una estrategia puede tener la mejor media del grupo y aun así perder dinero uno de cada cinco años. Y esto no es una apuesta que repites cien veces: la haces una, en enero, y vives con ella hasta diciembre.",
    respuesta: "Por eso no se calcula un resultado, se calculan diez mil y se mira la forma que tienen.",
    capa: "Capa 2 · 10.000 futuros con ruido",
  },
  {
    n: "03",
    Icon: IconAlert,
    titulo: "Pregunta a tres personas cuál es la mejor y te dan tres respuestas.",
    copy: "Finanzas mira el retorno sobre el capital. Operación mira cuántos ciclos te quedan y qué capacidad tendrá el banco en cinco años. Riesgo mira el peor escenario y qué pasa si incumples lo que le prometiste al operador de red. Las tres tienen razón, y no siempre señalan la misma casilla.",
    respuesta: "Cuando los tres coinciden, la decisión está sólida. Cuando no, ese desacuerdo es justo lo que hay que llevar al comité.",
    capa: "Capa 3 · tres lecturas independientes",
  },
];

const CAPACIDADES = [
  {
    titulo: "No solo predice: interviene.",
    copy: "Un modelo normal te da un número y ahí se acaba. Este coge la misma ventana histórica, le cambia la profundidad de descarga y vuelve a preguntar. La diferencia entre las dos respuestas es lo que aporta esa palanca, aislada de todo lo demás.",
  },
  {
    titulo: "No promedia el caos: lo simula.",
    copy: "En vez de inventar un escenario malo restando un 30 %, se inyectan tres ruidos con forma propia: la volatilidad del precio como lognormal, el riesgo de que ofertes y no te convoquen como distribución discreta, y el error del modelo como gaussiano. El escenario malo ya no es un número redondo: es el percentil 10 de diez mil ejecuciones.",
  },
  {
    titulo: "No entrega un gráfico: entrega una decisión defendible.",
    copy: "Tres modelos independientes leen las mismas cifras desde Finanzas, Operación y Riesgo. Y un guardarraíl retira cualquier frase que contradiga los números que tiene al lado, en vez de dejarla pasar. Lo que llega al comité se puede discutir línea por línea.",
  },
];

export function ProblemaSection({ fase, summary, ranking = [] }) {
  const n = (v, d = 0) => Number(v || 0).toLocaleString("es-ES", { maximumFractionDigits: d });
  const usd = (v) => (v < 0 ? "-" : "+") + "$" + n(Math.abs(v));

  /* La cifra del error sale del ranking, no esta escrita a mano: si cambian
     los datos, cambia sola. Es lo que convierte "hay que decidir bien" en algo
     que se siente. */
  const mejor = ranking[0];
  const intuitiva = ranking.find((r) => r.decision === "Arbitraje agresivo");
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
            Una batería, un año,<br />y cuatro formas de operarla.
          </h2>
          <p className="problema__lede">
            Imagina que operas una batería de 20 MW conectada a la red. Tienes
            cuatro formas de exprimirla este año y solo puedes elegir una. No hay
            ensayo general: la batería es una y el año pasa una sola vez.
          </p>

          {brecha != null && (
            <div className="problema__coste">
              <span className="label">Lo que cuesta elegir con el estómago</span>
              <strong className="problema__coste-cifra">{usd(brecha)}</strong>
              <p>
                Esa es la distancia entre <b>{mejor.decision}</b>, que la simulación
                deja primera con {usd(Number(mejor.expected_profit_usd))}, y{" "}
                <b>Arbitraje agresivo</b>, que es la que elegirías tú, yo y
                cualquiera mirando solo cuánto factura. Termina en{" "}
                {usd(Number(intuitiva.expected_profit_usd))}. Misma batería, mismo año,
                misma red.
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
              Aquí está el problema. Una batería de red es una inversión de varios
              millones cuyo retorno depende de cómo la operes cada día durante diez
              años. Y en la mayoría de los casos esa estrategia se fija con la misma
              herramienta con la que se cuadra el presupuesto de la oficina: tres
              escenarios en un Excel, puestos a ojo.
            </p>
            <p>
              El problema no es Excel. Es que <b>los escenarios se inventan en vez
              de derivarse</b>. Nadie sabe decirte por qué el escenario malo es un
              30 % peor, ni qué probabilidad tiene de pasar, ni cuántas veces de
              cada cien acabas perdiendo dinero. Y si no sabes eso, no estás
              decidiendo: estás apostando con vocabulario financiero.
            </p>
          </div>
        </div>

        {/* El activo. Aqui vive el mecanismo del caso y hay que dejarlo sin
            jerga: si esto no se entiende, no se entiende nada de lo que sigue. */}
        <div className="problema__activo">
          <div className="problema__activo-texto">
            <h3 className="problema__sub">
              Compra barato, vende caro. Y se gasta al hacerlo.
            </h3>
            <p>
              En palabras llanas: cuando la luz está tirada de precio, la batería
              carga. Cuando se dispara, descarga y se queda la diferencia. Eso,
              multiplicado por los megavatios que mueve, es todo el ingreso.
            </p>
            <p>
              Si fuera solo eso, no habría nada que decidir: cargarías y
              descargarías sin parar. Pero hay un tercer actor que casi nunca entra
              en el Excel, y es el que rompe el caso.
            </p>
            <p>
              <b>Cada ciclo desgasta las celdas. Y no lo hace en línea recta:
              descargar el doble de profundo no cuesta el doble de desgaste, cuesta
              unas cuatro veces más.</b> El desgaste crece con el cuadrado de la
              profundidad.
            </p>
            <p>
              ¿Y dónde aparece ese coste? En ningún sitio, hasta que es tarde. No
              está en la liquidación del día. Está tres años después, en una batería
              que ya no entrega los 80 MWh que prometía. Por eso la estrategia que
              más factura puede ser la que destruye el activo: gana hoy pagándolo con
              vida útil que nadie apuntó en ninguna parte.
            </p>
          </div>

          <ol className="mecanismo">
            <li>
              <span className="mecanismo__paso">Precio bajo</span>
              <b>Carga</b>
              <span>Absorbe energía barata de la red</span>
            </li>
            <li>
              <span className="mecanismo__paso">Precio alto</span>
              <b>Descarga</b>
              <span>La entrega y se queda el diferencial</span>
            </li>
            <li className="mecanismo--coste">
              <span className="mecanismo__paso">Siempre</span>
              <b>Desgaste</b>
              <span>Cada ciclo consume vida útil que no vuelve. Y nadie lo factura.</span>
            </li>
          </ol>

          <dl className="problema__ficha">
            <div><dt>Potencia</dt><dd>20 <span>MW</span></dd></div>
            <div><dt>Energía</dt><dd>80 <span>MWh</span></dd></div>
            {summary && (
              <>
                <div>
                  <dt>Ventanas</dt>
                  <dd>{n(summary.rows)} <span>horas de despacho</span></dd>
                </div>
                <div>
                  <dt>Precio medio</dt>
                  <dd>{n(summary.precio_spot_medio, 1)} <span>USD/MWh</span></dd>
                </div>
                <div>
                  <dt>Diferencial</dt>
                  <dd>{n(summary.diferencial_medio, 1)} <span>USD/MWh medio</span></dd>
                </div>
                <div>
                  <dt>Ciclos</dt>
                  <dd>{n(summary.ciclos_consumidos)} <span>consumidos en el histórico</span></dd>
                </div>
              </>
            )}
          </dl>
        </div>

        {/* Las cuatro candidatas, con su inversion. Sin el coste al lado, la
            comparacion no significa nada. */}
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

        {/* Las tres razones. Cada una justifica una capa: si quitas la razon,
            sobra la capa. */}
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

        {/* Que hace el sistema que un Excel no puede. Sin este bloque el lector
            entiende el problema pero no por que la solucion es distinta. */}
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
