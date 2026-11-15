import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

const apiProxy = {
  "/api": {
    target: process.env.ALAIRAX_API_PROXY_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, "") || "/",
  },
};

const onVercel = process.env.VERCEL === "1";

export default defineConfig({
  base: onVercel ? "/" : "/SpaceApps-AlairaX/",
  define: {
    __API_BASE_DEFAULT__: JSON.stringify(onVercel ? "/api" : ""),
  },
  plugins: [tailwindcss(), react()],
  server: { host: "127.0.0.1", port: 5173, proxy: apiProxy },
  preview: { host: "127.0.0.1", port: 4173, proxy: apiProxy },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
