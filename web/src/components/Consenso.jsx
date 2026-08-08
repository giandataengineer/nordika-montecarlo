import { Panel } from "./Blocks";
import { IconAlert, IconCheck, IconLayers } from "./Icons";

const ETIQUETA = { finanzas: "Finanzas", operacion: "Operación", riesgo: "Riesgo" };

/* El desacuerdo entre roles es el dato con más valor de toda la pantalla:
   significa que la elección depende de qué prioriza quien decide, no de los
   números. Por eso tiene su propio bloque y no va escondido en una nota. */
export function Consenso({ payload }) {
  const m = payload?.multirol;
  if (!m?.agregacion) return null;

  const { agregacion, lecturas = [] } = m;
  const conLlm = lecturas.filter((l) => l.fuente === "llm");
  const fallidos = lecturas.filter((l) => l.fuente !== "llm");

  const estado =
    agregacion.modo === "determinista" ? "neutro" : agregacion.consenso ? "acuerdo" : "desacuerdo";

  const Icono = estado === "desacuerdo" ? IconAlert : estado === "acuerdo" ? IconCheck : IconLayers;

  return (
    <Panel
      eyebrow="Tres lecturas · modelos independientes"
      title={
        estado === "desacuerdo"
          ? "Los roles no coinciden"
          : estado === "acuerdo"
            ? "Los tres roles coinciden"
            : "Lecturas deterministas"
      }
      className={`consenso consenso--${estado}`}
    >
      <p className="panel__copy">{agregacion.veredicto}</p>

      {conLlm.length > 0 && (
        <div className="consenso__grid">
          {conLlm.map((l) => (
            <article className="voto" key={l.rol}>
              <div className="voto__head">
                <span className="label">{ETIQUETA[l.rol] ?? l.rol}</span>
                <span className="voto__modelo">{(l.modelo || "").replace(/:free$/, "")}</span>
              </div>
              <p className="voto__eleccion">
                <Icono style={{ width: 15, height: 15 }} />
                {l.decision_elegida}
              </p>
              {l.headline && <p className="voto__headline">{l.headline}</p>}
              {l.coherencia?.frases_retiradas > 0 && (
                <p className="voto__aviso">
                  <IconAlert style={{ width: 13, height: 13 }} />
                  {l.coherencia.frases_retiradas} frase
                  {l.coherencia.frases_retiradas === 1 ? "" : "s"} retirada
                  {l.coherencia.frases_retiradas === 1 ? "" : "s"} por contradecir las cifras
                </p>
              )}
            </article>
          ))}
        </div>
      )}

      {fallidos.length > 0 && (
        <div className="consenso__fallos">
          <span className="label">Roles sin modelo disponible</span>
          <ul>
            {fallidos.map((l) => (
              <li key={l.rol}>
                <b>{ETIQUETA[l.rol] ?? l.rol}</b> · {l.motivo}
              </li>
            ))}
          </ul>
        </div>
      )}

      <span className="card__foot label">
        {m.desde_cache && "Lecturas reutilizadas de la última ejecución · "}
        {m.proveedores_configurados?.length
          ? `Proveedores activos: ${m.proveedores_configurados.join(" · ")}`
          : "Sin claves configuradas: el informe usa el camino determinista con guardarraíl"}
      </span>
    </Panel>
  );
}
