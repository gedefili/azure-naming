/*
 * Repository: azure-naming
 * Path: web/src/api/useApiClient.ts
 * Purpose: Hook returning a memoized API client bound to the current token
 * Author: GitHub Copilot
 * Created: 2026-04-26
 * Last-Modified: 2026-04-26
 * Version: 0.1.0
 */
import { useMemo } from "react";
import { useAccessToken } from "../auth/useAccessToken";
import { createApiClient, type ApiClient } from "./client";

export function useApiClient(): ApiClient {
  const getToken = useAccessToken();
  return useMemo(() => createApiClient(getToken), [getToken]);
}
