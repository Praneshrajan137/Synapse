import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const here = dirname(fileURLToPath(import.meta.url));

// `@chromatic` resolves to the SYNAPSE Chromatic System's generated artifacts
// (the portable colour core). `server.fs.allow` lets Vite serve them from
// outside the frontend root.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@chromatic": resolve(here, "../design-system/color/dist"),
    },
  },
  server: {
    port: 3001,
    fs: { allow: [resolve(here, "..")] },
    proxy: {
      "/api": "http://localhost:8085",
      "/ws": { target: "ws://localhost:8085", ws: true },
    },
  },
});
