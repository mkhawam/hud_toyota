import { resolve } from "node:path";
import { defineConfig } from "vite";
import solid from "vite-plugin-solid";

// Dev server proxies API + WebSocket to the Python backend so
// `npm run dev` + `python -m hud --source sim` just work together.
// Multi-page build: / is the kiosk HUD, /settings the phone settings page
// (FastAPI's StaticFiles(html=True) serves dist/settings/ automatically).
export default defineConfig({
  plugins: [solid()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        settings: resolve(__dirname, "settings/index.html"),
        trips: resolve(__dirname, "trips/index.html"),
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
