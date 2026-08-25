import { Panel } from "./Blocks";

/* La capa SQL, a la vista.
   Estaba en el repo desde el principio y no se veia en la consola: quien abria
   la pagina no sabia que el analisis descriptivo salia de DuckDB con CTEs y
   funciones de ventana. Se enseña la consulta al lado de su resultado, que es
   la unica forma de que se lea como trabajo y no como una linea del stack. */

function Tabla({ columnas, filas }) {
  const fmt = (v) => {
    if (typeof v !== "number") return String(v ?? "");
    if (Number.isInteger(v)) return v.toLocaleString("es-ES");
    return v.toLocaleString("es-ES", { maximumFractionDigits: 4 });
  };
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>{columnas.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i}>{columnas.map((c) => <td key={c}>{fmt(f[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SqlSection({ payload }) {
  const capa = payload?.sql;
  const consultas = capa?.consultas ?? [];
  if (consultas.length === 0) return null;

  return (
    <section className="section sql" id="sql">
      <div className="shell section__inner">
        <span className="label">La capa SQL</span>
        <h2 className="display sql__titulo">
          El descriptivo no sale<br />de pandas. Sale de SQL.
        </h2>
        <p className="sql__lede">
          Las agregaciones del caso viven en <code>sql/*.sql</code> y corren con DuckDB
          directamente sobre el CSV, sin paso de ingesta que mantener. El día que el
          histórico no quepa en memoria, esas mismas consultas van contra Postgres
          cambiando la conexión. Aquí van tres, con lo que devuelven.
        </p>

        <div className="sql__lista">
          {consultas.map((c) => (
            <Panel key={c.archivo} eyebrow={c.archivo} title={c.titulo}>
              <p className="panel__copy">{c.proposito}</p>
              <pre className="sql__codigo"><code>{c.sql}</code></pre>
              <Tabla columnas={c.columnas} filas={c.filas} />
            </Panel>
          ))}
        </div>
      </div>
    </section>
  );
}
