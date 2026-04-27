/*
 * Repository: azure-naming
 * Path: web/src/components/ClaimDrawer.test.tsx
 * Purpose: Tests for ClaimDrawer form submission and error rendering
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const claimMock = vi.fn();
vi.mock("../api/useApiClient", () => ({
  useApiClient: () => ({
    listClaims: vi.fn(),
    claim: claimMock,
    release: vi.fn(),
    remediate: vi.fn(),
    audit: vi.fn(),
  }),
}));

import { ClaimDrawer } from "./ClaimDrawer";
import { ApiError } from "../api/client";
import { withProviders } from "../test-utils";

describe("ClaimDrawer", () => {
  beforeEach(() => {
    claimMock.mockReset();
  });

  it("returns null when closed", () => {
    const { container } = render(withProviders(<ClaimDrawer open={false} onClose={() => undefined} />));
    expect(container.firstChild).toBeNull();
  });

  it("submits the form and calls onClose on success", async () => {
    claimMock.mockResolvedValueOnce({ name: "x" });
    const onClose = vi.fn();
    render(withProviders(<ClaimDrawer open onClose={onClose} />));

    await userEvent.type(screen.getByLabelText(/resource type/i), "storage_account");
    await userEvent.click(screen.getByRole("button", { name: /^claim$/i }));

    await waitFor(() => expect(claimMock).toHaveBeenCalled());
    expect(claimMock.mock.calls[0]![0]).toMatchObject({
      resource_type: "storage_account",
      region: "wus2",
      environment: "dev",
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("renders ApiError body in error state", async () => {
    claimMock.mockRejectedValueOnce(new ApiError(400, "name already claimed"));
    render(withProviders(<ClaimDrawer open onClose={() => undefined} />));
    await userEvent.type(screen.getByLabelText(/resource type/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /^claim$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("name already claimed");
  });

  it("renders generic error for non-ApiError", async () => {
    claimMock.mockRejectedValueOnce(new Error("network"));
    render(withProviders(<ClaimDrawer open onClose={() => undefined} />));
    await userEvent.type(screen.getByLabelText(/resource type/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /^claim$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/network/);
  });

  it("Cancel calls onClose without submitting", async () => {
    const onClose = vi.fn();
    render(withProviders(<ClaimDrawer open onClose={onClose} />));
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
    expect(claimMock).not.toHaveBeenCalled();
  });
});
