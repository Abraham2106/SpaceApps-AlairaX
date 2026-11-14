import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/SpaceApps-AlairaX/",
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5173 },
  preview: { host: "127.0.0.1", port: 4173 },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
