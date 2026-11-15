import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/SpaceApps-AlairaX/",
  plugins: [tailwindcss(), react()],
  server: { host: "127.0.0.1", port: 5173 },
  preview: { host: "127.0.0.1", port: 4173 },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
