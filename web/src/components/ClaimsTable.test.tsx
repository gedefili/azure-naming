/*
 * Repository: azure-naming
 * Path: web/src/components/ClaimsTable.test.tsx
 * Purpose: Tests for ClaimsTable rendering and action callbacks
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ClaimsTable } from "./ClaimsTable";
import type { ClaimSummary } from "../api/client";

const baseClaim: ClaimSummary = {
  name: "stwus2dev01",
  resource_type: "storage_account",
  region: "wus2",
  environment: "dev",
  in_use: true,
  claim_state: "claimed",
  claimed_by: "alice@sanmar.com",
  claimed_at: "2026-04-26T00:00:00Z",
};

describe("ClaimsTable", () => {
  it("renders empty state with no items", () => {
    render(<ClaimsTable items={[]} />);
    expect(screen.getByText(/no claims/i)).toBeInTheDocument();
  });

  it("hides Owner column unless showOwner=true", () => {
    const { rerender } = render(<ClaimsTable items={[baseClaim]} />);
    expect(screen.queryByText("Owner")).toBeNull();
    rerender(<ClaimsTable items={[baseClaim]} showOwner />);
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText(baseClaim.claimed_by!)).toBeInTheDocument();
  });

  it("renders Release button only when in_use AND onRelease supplied", async () => {
    const onRelease = vi.fn();
    render(<ClaimsTable items={[baseClaim]} onRelease={onRelease} />);
    const button = screen.getByRole("button", { name: /release/i });
    await userEvent.click(button);
    expect(onRelease).toHaveBeenCalledWith(baseClaim);
  });

  it("does not render Release for released claims", () => {
    render(
      <ClaimsTable
        items={[{ ...baseClaim, in_use: false }]}
        onRelease={() => undefined}
      />,
    );
    expect(screen.queryByRole("button", { name: /release/i })).toBeNull();
  });

  it("renders Purge button when onPurge supplied", async () => {
    const onPurge = vi.fn();
    render(<ClaimsTable items={[baseClaim]} onPurge={onPurge} />);
    await userEvent.click(screen.getByRole("button", { name: /purge/i }));
    expect(onPurge).toHaveBeenCalledWith(baseClaim);
  });

  it("renders em-dashes for missing optional fields", () => {
    const claim: ClaimSummary = { name: "x" };
    render(<ClaimsTable items={[claim]} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
