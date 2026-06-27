import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 8000 runs the backend, 5173 runs the frontend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Same-origin proxy for CORS errors. 
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/assets": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
