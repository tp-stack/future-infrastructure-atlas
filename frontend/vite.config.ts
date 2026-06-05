import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/maplibre-gl")) {
            return "vendor-maplibre";
          }
          if (id.includes("node_modules/pmtiles")) {
            return "vendor-pmtiles";
          }
        },
      },
    },
  },
});
