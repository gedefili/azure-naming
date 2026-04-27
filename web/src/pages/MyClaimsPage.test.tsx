/*
 * Repository: azure-naming
 * Path: web/src/pages/MyClaimsPage.test.tsx
 * Purpose: Tests for the My Claims page query + release flow
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiMock = {
  listClaims: vi.fn(),
  claim: vi.fn(),
  release: vi.fn(),
  remediate: vi.fn(),
  audit: vi.fn(),
};

vi.mock("../api/useApiClient", () => ({ useApiClient: () => apiMock }));

import { MyClaimsPage } from "./MyClaimsPage";
import { withProviders } from "../test-utils";

describe("MyClaimsPage", () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((m) => m.mockReset?.());
    apiMock.listClaims.mockResolvedValue({
      items: [
        {
          name: "stwus2dev01",
          resource_type: "storage_account",
          region: "wus2",
          environment: "dev",
          in_use: true,
          claim_state: "claimed",
          claimed_at: "2026-04-26T00:00:00Z",
        },
      ],
      count: 1,
      scope: "me",
      is_admin: false,
    });
  });

  it("renders rows from the listClaims query", async () => {
    render(withProviders(<MyClaimsPage />));
    expect(await screen.findByText("stwus2dev01")).toBeInTheDocument();
  });

  it("opens the release dialog and calls api.release on confirmation", async () => {
    apiMock.release.mockResolvedValue(undefined);
    render(withProviders(<MyClaimsPage />));
    await screen.findByText("stwus2dev01");
    const tableRelease = screen.getAllByRole("button", { name: /release/i });
    await userEvent.click(tableRelease[0]!);
    await userEvent.type(screen.getByLabelText(/type/i), "release");
    await userEvent.type(screen.getByLabelText(/reason/i), "decom");
    const dialog = screen.getByRole("dialog");
    const dialogConfirm = within(dialog).getByRole("button", { name: /^release$/i });
    await userEvent.click(dialogConfirm);
    await waitFor(() =>
      expect(apiMock.release).toHaveBeenCalledWith("stwus2dev01", "wus2", "dev", "decom"),
    );
  });

  it("opens the claim drawer when 'Claim a Name' is clicked", async () => {
    render(withProviders(<MyClaimsPage />));
    await screen.findByText("stwus2dev01");
    await userEvent.click(screen.getByRole("button", { name: /claim a name/i }));
    expect(screen.getByLabelText(/resource type/i)).toBeInTheDocument();
  });
});
