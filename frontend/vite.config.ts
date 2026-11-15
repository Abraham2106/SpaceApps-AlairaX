import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, "") || "/",
  },
};

export default defineConfig({
  base: "/SpaceApps-AlairaX/",
  plugins: [tailwindcss(), react()],
  server: { host: "127.0.0.1", port: 5173, proxy: apiProxy },
  preview: { host: "127.0.0.1", port: 4173, proxy: apiProxy },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
