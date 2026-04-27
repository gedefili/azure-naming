/*
 * Repository: azure-naming
 * Path: extensions/confluence/vitest.config.ts
 * Purpose: Vitest configuration with v8 coverage thresholds
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["src/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary", "lcov"],
      include: ["src/**/*.ts"],
      exclude: [
        "src/index.tsx",
        "src/tokenFetcher.ts",
        "src/**/*.test.ts",
      ],
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 85,
        statements: 90,
      },
    },
  },
});
