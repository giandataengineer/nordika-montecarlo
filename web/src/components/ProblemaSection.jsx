import { MarcaFase } from "./MarcaFase";
import { IconAlert, IconLayers, IconSimulate } from "./Icons";

/* Fase 01. El planteamiento va antes que cualquier grafica: primero se
   describe la empresa, despues los datos disponibles, despues las
   restricciones y solo al final lo que se desea averiguar. Sin enunciado, las
   graficas son adorno.
   El registro es el de un informe tecnico: frases completas, tercera persona y
   cifras que salen del historico. */

const CANDIDATAS = [
  {
    tipo: "La que propone el equipo",
    nombre: "Escalar paid social",
    inversion: "$9.000",
    tono: "riesgo",
    copy: "Consiste en aumentar el presupuesto de Meta y TikTok. Es la iniciativa que se propone con más frecuencia en las reuniones de crecimiento, porque aporta volumen desde el primer día y porque es la que mejor se refleja en los paneles de las plataformas.",
  },
  {
    tipo: "La de menor coste",
    nombre: "Optimizar la conversión del sitio",
    inversion: "$1.200",
    tono: "calma",
    copy: "Consiste en intervenir sobre la landing, la llamada a la acción, el lead magnet y el proceso de compra. No incorpora tráfico nuevo, sino que mejora el rendimiento del que ya llega. Es la de menor coste de ejecución y también la menos visible en los informes de campaña.",
  },
  {
    tipo: "La de menor riesgo",
    nombre: "Reactivación y remarketing",
    inversion: "$2.500",
    tono: "calma",
    copy: "Consiste en trabajar sobre la base de contactos que ya interactuó con la marca. El coste incremental es bajo y el ticket medio es alto, porque se dirige a personas que ya conocen el producto. Su techo lo determina el tamaño de esa base, que no crece por sí sola.",
  },
  {
    tipo: "La de mayor techo",
    nombre: "Abrir categoría nueva",
    inversion: "$12.000",
    tono: "riesgo",
    copy: "Consiste en incorporar una línea de producto con ticket superior en un mercado todavía sin explotar. Ofrece el techo más alto de las cuatro y es la única en la que el gasto se compromete por completo antes de conocer la respuesta del mercado, ya que exige catálogo, fotografía, stock y campañas de lanzamiento.",
  },
];

/* Lo que se desea averiguar. Cada pregunta se responde en una fase concreta
   de la consola, y ese vinculo se muestra al lado para que el recorrido se
   lea como un desarrollo y no como una sucesion de paneles. */
const PREGUNTAS = [
  { q: "¿El histórico cubre condiciones suficientemente diversas para modelar el comportamiento comercial?", fase: "Fase 02" },
  { q: "¿Qué probabilidad de conversión tiene cada oportunidad y con qué capacidad de discriminación se estima?", fase: "Fase 03" },
  { q: "¿Cuál es el ingreso esperado de las oportunidades que llegan a convertir?", fase: "Fase 03" },
  { q: "¿Cuánto aporta cada palanca por separado, medida contra su propio escenario base?", fase: "Fase 03" },
  { q: "¿Cuál es el beneficio esperado de cada iniciativa y qué dispersión presenta?", fase: "Fase 04" },
  { q: "¿Con qué probabilidad termina en pérdidas cada una de las cuatro iniciativas?", fase: "Fase 04" },
  { q: "¿Cuál es el peor escenario razonable, entendido como el percentil 10 de la distribución?", fase: "Fase 04" },
  { q: "¿Se mantiene el orden de las iniciativas si se modifican los supuestos de incertidumbre?", fase: "Fase 04" },
  { q: "¿Qué iniciativa cumple el criterio de decisión de la dirección y cuánto cuesta elegir la intuitiva?", fase: "Fase 05" },
  { q: "¿Coinciden las lecturas de Finanzas, Growth y Riesgo sobre las mismas cifras?", fase: "Fase 05" },
];

const RAZONES = [
  {
    n: "01",
    Icon: IconLayers,
    titulo: "El histórico registra lo que ocurrió, nunca lo que habría ocurrido.",
    copy: "En los datos figura la campaña que se lanzó, con la landing que se utilizó y el presupuesto que se le destinó. No figura, en cambio, cuánto se habría vendido ese mismo martes con otra landing, porque esa versión nunca llegó a existir. Comparar iniciativas usando periodos distintos del histórico equivale a comparar situaciones que no coincidieron ni en el tiempo ni en las condiciones del mercado.",
    respuesta: "Por ese motivo el sistema no compara periodos: toma la misma oportunidad, modifica una única palanca y vuelve a estimar el resultado.",
    capa: "Capa 1 · uplift contrafactual",
  },
  {
    n: "02",
    Icon: IconSimulate,
    titulo: "Un valor único oculta el riesgo. Una distribución lo muestra.",
    copy: "El retorno de una iniciativa no es un número, sino un rango de resultados posibles. La ejecución puede retrasarse, la competencia puede pujar por el mismo inventario y el canal puede saturarse antes de lo previsto. Una iniciativa puede presentar la mejor media del grupo y, aun así, terminar en pérdidas uno de cada seis trimestres. El presupuesto, en cambio, se compromete una sola vez.",
    respuesta: "Por ese motivo no se calcula un resultado, sino diez mil, y la decisión se toma sobre la forma de la distribución que producen.",
    capa: "Capa 2 · 10.000 futuros con ruido",
  },
  {
    n: "03",
    Icon: IconAlert,
    titulo: "Cada área evalúa la misma cifra con un criterio distinto.",
    copy: "La dirección financiera atiende al retorno sobre el capital invertido y al plazo de recuperación. El área de crecimiento atiende al aprendizaje que deja cada palanca para los trimestres siguientes. El área de riesgo atiende al peor escenario y a la exposición si el canal se satura antes de lo previsto. Los tres criterios son legítimos y no siempre señalan la misma iniciativa.",
    respuesta: "Cuando las tres lecturas coinciden, la decisión queda respaldada. Cuando no coinciden, ese desacuerdo es precisamente lo que debe llevarse al comité.",
    capa: "Capa 3 · tres lecturas independientes",
  },
];

const CAPACIDADES = [
  {
    titulo: "Estima el efecto de intervenir, no solo el resultado esperado.",
    copy: "Un modelo de predicción convencional devuelve una estimación y ahí termina su función. Este sistema toma la misma oportunidad del histórico, sustituye la landing por la alternativa y vuelve a consultar al modelo. La diferencia entre ambas respuestas es la aportación de esa palanca, aislada del resto de factores.",
  },
  {
    titulo: "Simula la incertidumbre en lugar de promediarla.",
    copy: "En lugar de construir un escenario adverso restando un 30 % al resultado, se incorporan tres fuentes de incertidumbre con forma propia: la variabilidad de la demanda mediante una distribución lognormal, el riesgo de ejecución mediante una distribución discreta y el error del modelo mediante una gaussiana. El escenario adverso deja de ser un número redondo y pasa a ser el percentil 10 de diez mil ejecuciones.",
  },
  {
    titulo: "Entrega una decisión documentada, no un gráfico.",
    copy: "Tres modelos independientes interpretan las mismas cifras desde Finanzas, Growth y Riesgo. Un guardarraíl de coherencia revisa después cada frase generada contra los números que la acompañan y retira la que los contradice. El documento que llega al comité puede discutirse línea por línea.",
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
            Cuatro iniciativas<br />y un solo presupuesto.
          </h2>
          <p className="problema__lede">
            Vantara es un ecommerce que vende en seis mercados a través de siete
            canales de captación. Su unidad de captación de pago debe asignar el
            presupuesto del próximo trimestre y solo puede financiar una de las
            cuatro iniciativas que tiene sobre la mesa. La decisión se toma una
            única vez, porque el trimestre no se repite.
          </p>
        </header>

        {/* Enunciado formal: contexto, datos, restricciones y preguntas. */}
        <div className="problema__enunciado">
          <div className="problema__enunciado-texto">
            <span className="label">Contexto de la operación</span>
            <h3 className="problema__sub problema__sub--ancho">
              Qué información hay sobre la mesa antes de decidir.
            </h3>
            <p>
              El histórico disponible reúne 20.000 oportunidades comerciales
              registradas entre enero de 2024 y abril de 2026. En ese periodo la
              unidad generó 2,19 millones de dólares de ingreso atribuido, con una
              inversión publicitaria equivalente al 7,8 % de ese ingreso y una
              conversión media del 9,9 %. Cada oportunidad queda descrita por 28
              variables que recogen el canal por el que entró, la campaña que la
              originó, el segmento de cliente, el dispositivo, la geografía, el
              nivel de inversión vigente en ese momento y el desenlace comercial.
            </p>
            <p>
              El elemento sobre el que se hace el seguimiento es el presupuesto de
              captación de pago, que se asigna por trimestres y no admite reparto
              parcial entre iniciativas. Se sabe que el coste de captar una
              oportunidad no es constante, sino que crece a medida que se satura la
              audiencia del canal, de modo que un aumento del presupuesto no
              produce un aumento proporcional de las ventas. Se sabe además que los
              paneles de las plataformas publicitarias atribuyen una misma venta a
              más de un canal, por lo que la suma de las ventas que reportan supera
              a las ventas reales del ecommerce y no puede utilizarse como base de
              reparto.
            </p>
            <p>
              Ejecutar cada iniciativa tiene un coste fijo conocido: 1.200 dólares
              la optimización del sitio, 2.500 la reactivación de la base, 9.000 el
              escalado de paid social y 12.000 la apertura de una categoría nueva.
              La dirección establece como criterio de decisión que la iniciativa
              elegida no supere el 5 % de probabilidad de pérdida y que su percentil
              10 sea positivo. Con estas condiciones, se desea averiguar lo
              siguiente.
            </p>
          </div>

          <ol className="preguntas">
            {PREGUNTAS.map(({ q, fase: f }, i) => (
              <li key={q}>
                <span className="preguntas__n">{String(i + 1).padStart(2, "0")}</span>
                <p>{q}</p>
                <span className="preguntas__fase">{f}</span>
              </li>
            ))}
          </ol>
        </div>

        {brecha != null && (
          <div className="problema__coste">
            <span className="label">Lo que cuesta decidir por intuición</span>
            <strong className="problema__coste-cifra">{usd(brecha)}</strong>
            <p>
              Esa cifra es la diferencia entre <b>{mejor.decision}</b>, que la
              simulación sitúa en primer lugar con{" "}
              {usd(Number(mejor.expected_profit_usd))}, y{" "}
              <b>escalar paid social</b>, que termina en{" "}
              {usd(Number(intuitiva.expected_profit_usd))} pese a ser la iniciativa
              que casi cualquiera elegiría al mirar los paneles. Conviene subrayar
              que no se están comparando trimestres distintos ni equipos distintos:
              se trata del mismo trimestre, el mismo presupuesto y el mismo equipo,
              y la única diferencia está en dónde se decide poner el dinero.
            </p>
          </div>
        )}

        {/* El villano. Nombrarlo antes de presentar el metodo hace que el metodo
            se lea como respuesta y no como demo tecnica. */}
        <div className="problema__villano">
          <div>
            <span className="label">Cómo se decide esto en la práctica</span>
            <blockquote className="problema__cita">
              «Escenario malo, menos 30 %.<br />Escenario bueno, más 30 %.»
            </blockquote>
            <p className="problema__nota">
              La objeción a este método no es que sea optimista o pesimista, sino
              que ese 30 % no procede de ninguna medición.
            </p>
          </div>
          <div className="problema__villano-copy">
            <p>
              Un escenario construido de ese modo no permite saber qué probabilidad
              tiene de ocurrir, con qué frecuencia el resultado quedaría por debajo
              ni qué sucede cuando dos supuestos fallan al mismo tiempo. La cifra se
              elige porque es redonda, no porque se haya medido.
            </p>
            <p>
              A esa dificultad se suma la de la atribución. El panel de Meta informa
              de 400 ventas, el de Google de 350 y el de TikTok de 200, lo que suma
              950 ventas frente a las 600 que registró el ecommerce en el mismo
              periodo. Cada plataforma se atribuye por completo una venta en la que
              intervinieron varias.
            </p>
            <p>
              Desde que iOS exige permiso explícito para el rastreo y los
              navegadores bloquean las cookies de terceros, la confianza en la
              atribución entre canales <b>se sitúa por debajo del 50 %</b>, y el
              71 % de las marcas declara estar reduciendo su dependencia de esos
              datos. Decidir con tres supuestos elegidos a ojo y tres paneles que se
              contradicen entre sí <b>no es una decisión informada, sino una apuesta
              formulada en lenguaje financiero.</b>
            </p>
          </div>
        </div>

        {/* El mecanismo del caso: la saturacion de canal. */}
        <div className="problema__activo">
          <div className="problema__activo-texto">
            <h3 className="problema__sub">
              Por qué comprar más tráfico deja de compensar.
            </h3>
            <p>
              Cuando se incrementa el presupuesto de un canal, el volumen de visitas
              aumenta de inmediato y, durante un primer tramo, el coste por
              oportunidad se mantiene estable. El panel refleja ese crecimiento y la
              lectura inicial resulta favorable para todo el equipo.
            </p>
            <p>
              El problema aparece después. La audiencia con intención de compra de
              un canal es finita y, una vez alcanzada, el algoritmo amplía el
              público hacia perfiles con menor propensión a comprar. Llegar hasta
              ellos exige pujar más alto, de manera que el coste sube justo cuando
              la conversión empieza a bajar.
            </p>
            <p>
              <b>En este histórico el efecto se mide con claridad: al pasar del
              tramo medio al tramo saturado, el coste por oportunidad se duplica y
              la conversión se reduce a menos de la mitad.</b> El margen de
              contribución por oportunidad cae de 35,78 a 1,14 dólares.
            </p>
            <p>
              Ese deterioro no aparece en el panel del canal, que continúa
              contabilizando conversiones con normalidad. Solo se hace visible al
              comparar el ingreso obtenido con la inversión que lo produjo, que es
              precisamente la comparación que la atribución rota impide realizar con
              fiabilidad.
            </p>
          </div>

          <ol className="mecanismo">
            <li>
              <span className="mecanismo__paso">Tramo bajo</span>
              <b>$9,66</b>
              <span>por oportunidad. Convierte al 6,4 % y deja $35,44 de margen.</span>
            </li>
            <li>
              <span className="mecanismo__paso">Tramo alto</span>
              <b>$14,35</b>
              <span>por oportunidad. Convierte al 4,9 % y deja $23,20 de margen.</span>
            </li>
            <li className="mecanismo--coste">
              <span className="mecanismo__paso">Tramo saturado</span>
              <b>$20,56</b>
              <span>por oportunidad. Convierte al 2,8 % y deja $1,14 de margen.</span>
            </li>
          </ol>

          <dl className="problema__ficha">
            {summary && (
              <>
                <div>
                  <dt>Oportunidades</dt>
                  <dd>{n(summary.rows)} <span>en 28 meses de histórico</span></dd>
                </div>
                <div>
                  <dt>Ingreso atribuido</dt>
                  <dd>${n((summary.ingreso_usd ?? 0) / 1e6, 2)} M <span>en el periodo completo</span></dd>
                </div>
                <div>
                  <dt>Inversión</dt>
                  <dd>{n((summary.pct_inversion_sobre_ingreso ?? 0) * 100, 1)} % <span>sobre el ingreso</span></dd>
                </div>
                <div>
                  <dt>Conversión</dt>
                  <dd>{n((summary.conversion_rate ?? 0) * 100, 1)} % <span>media del histórico</span></dd>
                </div>
                <div>
                  <dt>Canales</dt>
                  <dd>{n(summary.channel_count)} <span>vías de captación activas</span></dd>
                </div>
                <div>
                  <dt>Ticket medio</dt>
                  <dd>${n(summary.avg_ticket_usd)} <span>por venta cerrada</span></dd>
                </div>
              </>
            )}
          </dl>
        </div>

        {/* Las cuatro candidatas, con su inversion. */}
        <div className="problema__candidatas">
          <span className="label">
            Las cuatro iniciativas · cada una falla por un motivo distinto
          </span>
          <div className="problema__grid">
            {CANDIDATAS.map((c) => (
              <article className={`candidata candidata--${c.tono}`} key={c.nombre}>
                <span className="candidata__tipo">{c.tipo}</span>
                <h4 className="candidata__nombre">{c.nombre}</h4>
                <span className="candidata__inversion">{c.inversion} de coste de ejecución</span>
                <p>{c.copy}</p>
              </article>
            ))}
          </div>
        </div>

        {/* Las tres razones. Cada una justifica una capa. */}
        <div className="problema__razones">
          <span className="label">
            Por qué no basta con revisar el histórico
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
          <span className="label">Qué aporta este sistema frente a una hoja de cálculo</span>
          <h3 className="problema__sub problema__sub--ancho">
            El objetivo no es un modelo que prediga, sino uno que además
            intervenga sobre el escenario, lo someta a incertidumbre y lo traduzca
            a una decisión que alguien pueda defender ante un comité.
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
            La iniciativa recomendada no es la más llamativa, sino la que sigue
            siendo rentable cuando se le retira la suerte.
          </p>
        </div>
      </div>
    </section>
  );
}
