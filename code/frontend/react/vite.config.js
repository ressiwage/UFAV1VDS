import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // dev: проксируем запросы к API
    proxy: {
      "/register": { target: "http://api:8000" },
      "/login":    { target: "http://api:8000" },
      "/user":     { target: "http://api:8000" },
      "/upload":   { target: "http://api:8000" },
      "/videos":   { target: "http://api:8000" },
    },
  },
  preview: {
    // prod-preview: тот же прокси
    proxy: {
      "/register": { target: "http://api:8000" },
      "/login":    { target: "http://api:8000" },
      "/user":     { target: "http://api:8000" },
      "/upload":   { target: "http://api:8000" },
      "/videos":   { target: "http://api:8000" },
    },
  },
});