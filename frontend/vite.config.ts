import { defineConfig } from "vite";

export default defineConfig({
  server: {
    // Send API-kall vidare til Python-backenden
    proxy: { "/api": "http://localhost:8000" },
  },
});
