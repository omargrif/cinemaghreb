import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Same-origin in dev: the backend (uvicorn, port 8000) needs no CORS round-trip.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
