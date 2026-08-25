/* Las cifras que la consola usa despues, explicadas antes de usarlas.
   Un informe tecnico define primero como se calcula cada indicador y como se
   relacionan entre si; sin eso, el lector llega a los paneles con vocabulario
   que nadie le ha traducido. */

const DEFINICIONES = [
  {
    n: "01",
    termino: "Uplift contrafactual",
    formula: "uplift = valor esperado con la palanca aplicada − valor esperado sin ella, sobre las mismas oportunidades",
    copy: "Mide lo que aporta una palanca cuando todo lo demás se mantiene constante. Se toman las oportunidades del histórico, se modifica una sola característica (por ejemplo, la variante de landing) y se vuelve a estimar el resultado con el modelo. La resta entre ambas estimaciones es el uplift. Al aplicarse sobre los mismos registros, no arrastra las diferencias de estacionalidad, canal o competencia que sí aparecen al comparar dos periodos distintos.",
  },
  {
    n: "02",
    termino: "Percentil 10 y percentil 90",
    formula: "P10 = resultado que deja por debajo al 10 % peor de los escenarios · P90 = el que deja por debajo al 90 %",
    copy: "Los 10.000 escenarios de cada iniciativa se ordenan de peor a mejor. El percentil 10 es el suelo razonable de la distribución y el percentil 90, su techo. La distancia entre ambos indica cuánto depende el resultado del escenario que toque: una banda estrecha señala un resultado predecible y una banda ancha, uno que se decide más por el entorno que por la ejecución.",
  },
  {
    n: "03",
    termino: "Probabilidad de pérdida",
    formula: "probabilidad de pérdida = escenarios con beneficio negativo ÷ escenarios simulados",
    copy: "Es la proporción de futuros en los que la iniciativa termina destruyendo margen. Una probabilidad del 17 % significa que, de cada cien trimestres con estas condiciones, en diecisiete la decisión habría salido cara. Es la cifra que la media esconde, porque una media alta puede convivir con una cola izquierda muy pesada.",
  },
  {
    n: "04",
    termino: "Retorno esperado (ROI)",
    formula: "ROI = beneficio esperado ÷ coste de ejecutar la iniciativa",
    copy: "Relaciona lo que se espera ganar con lo que cuesta poner la iniciativa en marcha. Es la medida que permite comparar una palanca barata con una cara sin quedarse solo con el importe absoluto: optimizar el sitio cuesta 1.200 dólares y abrir una categoría nueva, 12.000, de modo que el mismo beneficio no vale lo mismo en un caso que en el otro.",
  },
  {
    n: "05",
    termino: "Esperanza ajustada al riesgo",
    formula: "esperanza ajustada = media de los escenarios penalizada por el peso de la cola izquierda",
    copy: "Es el criterio con el que se ordena el ranking final. En lugar de premiar el techo del mejor escenario, descuenta la parte de la distribución que termina en pérdidas. Por eso la iniciativa ganadora puede no ser la de mayor máximo, sino la que mantiene un resultado aceptable en la mayor parte de los futuros simulados.",
  },
  {
    n: "06",
    termino: "Valor esperado de la información perfecta (EVPI)",
    formula: "EVPI = valor de elegir sabiendo el escenario − valor de elegir bajo incertidumbre",
    copy: "Responde a cuánto vale reducir la incertidumbre antes de decidir. Si supiéramos de antemano qué escenario va a ocurrir, elegiríamos en cada uno la mejor iniciativa; como no lo sabemos, elegimos siempre la misma. La diferencia entre ambas situaciones es el techo de lo que tiene sentido gastar en un piloto, en una prueba A/B o en mejores datos: pagar más que eso es pagar por encima de lo que la información puede aportar.",
  },
];

export function Definiciones() {
  return (
    <section className="section definiciones" id="definiciones">
      <div className="shell section__inner">
        <span className="label">Cómo se calcula cada cifra</span>
        <h2 className="display definiciones__titulo">
          Seis indicadores,<br />explicados antes de usarlos.
        </h2>
        <p className="definiciones__lede">
          Las fases siguientes se apoyan en seis medidas. Conviene fijar aquí qué
          significa cada una y cómo se obtiene, para que después baste con leer el
          número. Todas se calculan sobre los mismos 10.000 escenarios y sobre el
          mismo histórico de 20.000 oportunidades.
        </p>

        <ol className="definiciones__lista">
          {DEFINICIONES.map(({ n, termino, formula, copy }) => (
            <li key={n}>
              <span className="definiciones__n">{n}</span>
              <div>
                <h3 className="definiciones__termino">{termino}</h3>
                <p className="definiciones__formula">{formula}</p>
                <p className="definiciones__copy">{copy}</p>
              </div>
            </li>
          ))}
        </ol>

        {/* La relacion entre las dos cifras de riesgo es lo que mas se confunde
            al leer el ranking, asi que se explica aparte. */}
        <div className="definiciones__relacion">
          <h3 className="problema__sub">
            Cómo se relacionan el percentil 10 y la probabilidad de pérdida.
          </h3>
          <p>
            Ambas describen el riesgo, pero responden a preguntas distintas. La
            probabilidad de pérdida indica <b>con qué frecuencia</b> la iniciativa
            termina en números rojos, mientras que el percentil 10 indica{" "}
            <b>hasta dónde llega la caída</b> cuando eso ocurre. Una iniciativa
            puede perder dinero pocas veces y perder mucho cuando lo hace, o perder
            a menudo cantidades pequeñas.
          </p>
          <p>
            Leídas juntas permiten anticipar la exposición real del trimestre. Por
            eso el criterio de la dirección exige las dos condiciones a la vez: que
            la probabilidad de pérdida no supere el 5 % y que el percentil 10 se
            mantenga positivo. Cumplir solo una de las dos deja fuera la mitad del
            problema.
          </p>
        </div>
      </div>
    </section>
  );
}
