import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  build: {
    rollupOptions: {
      output: {
        // recharts pesa más que el resto de la app junta: va en su propio chunk
        manualChunks: { recharts: ["recharts"], motion: ["motion/react"] },
      },
    },
  },
});
