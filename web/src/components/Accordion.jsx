import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

/* Acordeón de una sola apertura: al abrir una pregunta se cierra la anterior,
   y el signo pasa de + a - con una transición de altura, no un fade. */
export function Accordion({ items }) {
  const [open, setOpen] = useState(0);

  return (
    <div>
      {items.map((item, i) => {
        const isOpen = open === i;
        return (
          <div className="q" key={item.q} data-open={isOpen}>
            <button
              className="q__top"
              type="button"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? -1 : i)}
            >
              <span className="q__n">Q{i + 1}</span>
              <span className="q__t">{item.q}</span>
              <span className="q__sign" aria-hidden="true" />
            </button>

            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  className="q__body"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
                >
                  <p>{item.a}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
