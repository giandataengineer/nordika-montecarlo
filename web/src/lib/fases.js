/* Las fases las define el backend en `payload.stages`. Tenerlas duplicadas en
   el front garantizaba que tarde o temprano dijeran cosas distintas: aquí solo
   se mapea cada clave del backend al ancla que usa la página. */
export const ANCLA = {
  // La Fase 01 es la seccion del problema, no la cabecera. Apuntarla a "top"
  // hacia que "recorrer las 5 fases" empezara en la Fase 02.
  briefing: "fase-00",
  ingesta: "fase-01",
  uplift: "fase-02",
  montecarlo: "fase-03",
  reporte: "fase-04",
};

export function fases(payload) {
  const stages = payload?.stages ?? [];
  return stages
    .filter((s) => ANCLA[s.key])
    .map((s) => ({
      key: s.key,
      id: ANCLA[s.key],
      eyebrow: s.eyebrow,
      title: s.title,
      tagline: s.tagline,
    }));
}

export function fase(payload, key) {
  return fases(payload).find((f) => f.key === key) ?? null;
}
