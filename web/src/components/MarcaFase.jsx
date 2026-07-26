/* Marcador de fase. Un solo componente para que el hero y todas las secciones
   se vean igual: número dominante en color de acento y nombre en mono al lado. */
export function MarcaFase({ eyebrow, title }) {
  const numero = String(eyebrow ?? "").replace(/\D/g, "") || "01";
  return (
    <span className="marca-fase">
      <b>{numero}</b>
      {title}
    </span>
  );
}
