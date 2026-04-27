/*
 * Repository: azure-naming
 * Path: web/src/api/errors.ts
 * Purpose: API error class used by the Naming Service HTTP client
 * Author: GitHub Copilot
 * Created: 2026-04-27
 * Last-Modified: 2026-04-27
 * Version: 0.1.0
 */

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * Thrown by the token provider when it triggered an interactive redirect.
 * Callers should treat this as a soft signal — the page is about to navigate
 * away and any pending operation should be cancelled silently.
 */
export class RedirectingError extends Error {
  constructor() {
    super("Authentication redirect in progress");
    this.name = "RedirectingError";
  }
}

/** True when `value` is an `ApiError`. */
export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
