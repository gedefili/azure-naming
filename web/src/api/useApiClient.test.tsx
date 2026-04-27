/*
 * Repository: azure-naming
 * Path: web/src/api/useApiClient.test.tsx
 * Purpose: Memoization test for useApiClient
 */
import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

const tokenProvider = vi.fn(async () => "TOKEN");
vi.mock("../auth/useAccessToken", () => ({
  useAccessToken: () => tokenProvider,
}));

import { useApiClient } from "./useApiClient";

describe("useApiClient", () => {
  it("returns a stable client across re-renders", () => {
    const { result, rerender } = renderHook(() => useApiClient());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
    expect(typeof first.listClaims).toBe("function");
  });
});
