/*
 * Repository: azure-naming
 * Path: web/src/pages/AllClaimsPage.test.tsx
 * Purpose: Tests for the admin AllClaimsPage purge flow
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

import { AllClaimsPage } from "./AllClaimsPage";
import { withProviders } from "../test-utils";

describe("AllClaimsPage", () => {
  beforeEach(() => {
    Object.values(apiMock).forEach((m) => m.mockReset?.());
    apiMock.listClaims.mockResolvedValue({
      items: [
        {
          name: "kvwus2prd01",
          resource_type: "key_vault",
          region: "wus2",
          environment: "prd",
          in_use: false,
          claim_state: "released",
          claimed_by: "bob@sanmar.com",
        },
      ],
      count: 1,
      scope: "all",
      is_admin: true,
    });
  });

  it("calls listClaims with owner=all", async () => {
    render(withProviders(<AllClaimsPage />));
    await screen.findByText("kvwus2prd01");
    expect(apiMock.listClaims).toHaveBeenCalledWith(
      expect.objectContaining({ owner: "all" }),
    );
  });

  it("purges through ConfirmDialog with reason", async () => {
    apiMock.remediate.mockResolvedValue(undefined);
    render(withProviders(<AllClaimsPage />));
    await screen.findByText("kvwus2prd01");
    const purgeButtons = screen.getAllByRole("button", { name: /purge/i });
    await userEvent.click(purgeButtons[0]!);
    await userEvent.type(screen.getByLabelText(/type/i), "purge");
    await userEvent.type(screen.getByLabelText(/reason/i), "drift");
    const dialog = screen.getByRole("dialog");
    const dialogConfirm = within(dialog).getByRole("button", { name: /^purge$/i });
    await userEvent.click(dialogConfirm);
    await waitFor(() =>
      expect(apiMock.remediate).toHaveBeenCalledWith(
        "kvwus2prd01",
        "wus2",
        "prd",
        "purge",
        "drift",
      ),
    );
  });
});
