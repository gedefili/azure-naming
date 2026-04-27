/*
 * Repository: azure-naming
 * Path: web/src/api/errors.test.ts
 * Purpose: Tests for ApiError shape and helpers
 */
import { describe, expect, it } from "vitest";
import { ApiError, RedirectingError, isApiError } from "./errors";

describe("ApiError", () => {
  it("captures status and body", () => {
    const err = new ApiError(403, "denied");
    expect(err.status).toBe(403);
    expect(err.body).toBe("denied");
    expect(err.message).toBe("API error 403");
    expect(err.name).toBe("ApiError");
  });

  it("respects custom message", () => {
    const err = new ApiError(401, "", "Not signed in");
    expect(err.message).toBe("Not signed in");
  });
});

describe("RedirectingError", () => {
  it("identifies the redirect state", () => {
    const err = new RedirectingError();
    expect(err.name).toBe("RedirectingError");
    expect(err.message).toMatch(/redirect/i);
  });
});

describe("isApiError", () => {
  it("returns true only for ApiError instances", () => {
    expect(isApiError(new ApiError(500, ""))).toBe(true);
    expect(isApiError(new Error("x"))).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError("string")).toBe(false);
  });
});
