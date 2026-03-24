import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": {
        // in docker
        target: "http://api:8000",
        // local
        // target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
