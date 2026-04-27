/*
 * Repository: azure-naming
 * Path: web/src/test-utils.tsx
 * Purpose: Shared rendering helpers for component + page tests
 */
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "./theme/ThemeProvider";
import { MemoryStorage } from "./lib/storage";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function withProviders(
  children: ReactNode,
  client: QueryClient = makeQueryClient(),
): ReactNode {
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ThemeProvider seed="alice" storage={new MemoryStorage()}>
          {children}
        </ThemeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
