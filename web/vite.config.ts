/*
 * Repository: azure-naming
 * Path: web/vite.config.ts
 * Purpose: Vite config for the Azure Naming web SPA
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBase = env.VITE_NAMING_API_BASE_URL ?? "http://localhost:7071";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiBase,
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      target: "es2022",
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            msal: ["@azure/msal-browser", "@azure/msal-react"],
            tanstack: ["@tanstack/react-query"],
          },
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test-setup.ts"],
      css: false,
      coverage: {
        provider: "v8",
        reporter: ["text", "html", "json-summary", "lcov"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "src/main.tsx",
          "src/vite-env.d.ts",
          "src/test-setup.ts",
          "src/**/*.test.{ts,tsx}",
          "src/**/__mocks__/**",
        ],
        thresholds: {
          lines: 90,
          functions: 90,
          branches: 85,
          statements: 90,
        },
      },
    },
  };
});
