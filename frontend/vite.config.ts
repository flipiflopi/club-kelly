import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://backend:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
