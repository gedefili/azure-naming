/*
 * Repository: azure-naming
 * Path: web/src/lib/json.test.ts
 * Purpose: Unit tests for safeJsonParse
 */
import { describe, expect, it } from "vitest";
import { safeJsonParse } from "./json";

describe("safeJsonParse", () => {
  it("parses valid JSON", () => {
    expect(safeJsonParse('{"a":1}', null)).toEqual({ a: 1 });
  });
  it("returns fallback for empty string", () => {
    expect(safeJsonParse("", { ok: true })).toEqual({ ok: true });
  });
  it("returns fallback on parse error", () => {
    expect(safeJsonParse("{not json}", "fallback")).toBe("fallback");
  });
});
