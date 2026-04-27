/*
 * Repository: azure-naming
 * Path: web/src/main.tsx
 * Purpose: SPA entrypoint — MSAL provider, query client, theme provider, router
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { MsalProvider } from "@azure/msal-react";
import { EventType, type EventMessage } from "@azure/msal-browser";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { msalInstance } from "./auth/msalConfig";
import { ThemeProvider } from "./theme/ThemeProvider";
import "./styles/global.css";

// Optionally enable login state persistence across page reloads
msalInstance.addEventCallback((event: EventMessage) => {
  if (event.eventType === EventType.LOGIN_SUCCESS && event.payload && "account" in event.payload) {
    msalInstance.setActiveAccount(event.payload.account ?? null);
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

void msalInstance.initialize().then(() => {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0 && !msalInstance.getActiveAccount()) {
    msalInstance.setActiveAccount(accounts[0]!);
  }

  const seed = msalInstance.getActiveAccount()?.username;

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <MsalProvider instance={msalInstance}>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider seed={seed}>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ThemeProvider>
        </QueryClientProvider>
      </MsalProvider>
    </React.StrictMode>,
  );
});
