/* Set de iconos propio, trazo de 1.6 sobre rejilla de 24, un solo estilo.
   Nada de emoji ni de mezclar familias. */

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export const IconBriefing = (p) => (
  <svg {...base} {...p}>
    <path d="M5 4h9l5 5v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z" />
    <path d="M14 4v5h5" />
    <path d="M8 13h8" />
    <path d="M8 17h5" />
  </svg>
);

export const IconLoad = (p) => (
  <svg {...base} {...p}>
    <path d="M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Z" />
    <path d="M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </svg>
);

export const IconModel = (p) => (
  <svg {...base} {...p}>
    <path d="M3 18 9 12l4 4 8-8.5" />
    <path d="M15 7.5h6v6" />
  </svg>
);

export const IconSimulate = (p) => (
  <svg {...base} {...p}>
    <path d="M4 20v-6" />
    <path d="M9 20V8" />
    <path d="M14 20v-9" />
    <path d="M19 20V5" />
    <path d="M3 20h18" />
  </svg>
);

export const IconDecide = (p) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="13.5" r="6.5" />
    <path d="m9.3 13.5 1.9 1.9 3.5-3.6" />
    <path d="M12 3.5v2.5" />
    <path d="M6.9 5.4 8.5 7.4" />
    <path d="M17.1 5.4 15.5 7.4" />
  </svg>
);

export const IconArrowDown = (p) => (
  <svg {...base} {...p}>
    <path d="M12 5v14" />
    <path d="m6 13 6 6 6-6" />
  </svg>
);

export const IconArrowRight = (p) => (
  <svg {...base} {...p}>
    <path d="M5 12h14" />
    <path d="m13 6 6 6-6 6" />
  </svg>
);

export const IconTrendUp = (p) => (
  <svg {...base} {...p}>
    <path d="m4 16 5-5 3 3 8-8" />
    <path d="M14 6h6v6" />
  </svg>
);

export const IconMenu = (p) => (
  <svg {...base} {...p}>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </svg>
);

/* Marca del proyecto. La montaña anterior no decía nada del método: esto es
   una nube de puntos aleatorios que se acumula bajo la curva de la distribución
   resultante, que es literalmente lo que hace una simulación Monte Carlo. */
export const IconMontecarlo = (p) => (
  <svg viewBox="0 0 24 24" fill="none" {...p}>
    <path
      d="M2.5 18.5c3.2 0 3.6-11 9.5-11s6.3 11 9.5 11"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <g fill="currentColor">
      <circle cx="12" cy="11.4" r="1.05" />
      <circle cx="9.6" cy="13.6" r="0.85" />
      <circle cx="14.5" cy="13.4" r="0.85" />
      <circle cx="12.1" cy="15.4" r="0.8" />
      <circle cx="7.5" cy="16.2" r="0.7" />
      <circle cx="16.7" cy="16" r="0.7" />
      <circle cx="10.2" cy="17.6" r="0.6" />
      <circle cx="14" cy="17.7" r="0.6" />
      <circle cx="5.4" cy="18" r="0.5" />
      <circle cx="18.7" cy="18.1" r="0.5" />
    </g>
  </svg>
);

// alias: la marca se seguia importando con el nombre antiguo en varios sitios
export const IconPeak = IconMontecarlo;

export const IconAlert = (p) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5" />
    <path d="M12 16.5h.01" />
  </svg>
);

export const IconCheck = (p) => (
  <svg {...base} {...p}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const IconLayers = (p) => (
  <svg {...base} {...p}>
    <path d="m12 3 9 5-9 5-9-5 9-5Z" />
    <path d="m3 13 9 5 9-5" />
  </svg>
);

export const IconSpread = (p) => (
  <svg {...base} {...p}>
    <path d="M3 20h18" />
    <path d="M6 20v-4" />
    <path d="M10 20V9" />
    <path d="M14 20V4" />
    <path d="M18 20v-8" />
  </svg>
);
