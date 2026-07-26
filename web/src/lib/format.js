/* Los campos del backend llevan sufijo _usd porque el dataset sintético se
   generó en euros. La consola los presenta en dólares: es un cambio de
   etiqueta sobre datos sintéticos, no una conversión de divisa. */
export const usd = (n, max = 0) =>
  `$${Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: max })}`;

export const usdK = (n) => {
  const v = Number(n || 0);
  return Math.abs(v) >= 1000 ? `$${(v / 1000).toFixed(1)}k` : `$${v.toFixed(0)}`;
};

export const pct = (n, d = 1) => `${(Number(n || 0) * 100).toFixed(d)}%`;
export const pctRaw = (n, d = 1) => `${Number(n || 0).toFixed(d)}%`;
export const num = (n) => Number(n || 0).toLocaleString("en-US");
export const roi = (n) => `${Number(n || 0).toFixed(2)}x`;
