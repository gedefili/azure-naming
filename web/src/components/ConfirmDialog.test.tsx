/*
 * Repository: azure-naming
 * Path: web/src/components/ConfirmDialog.test.tsx
 * Purpose: Tests for the typed-confirmation modal
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmDialog } from "./ConfirmDialog";

const baseProps = {
  open: true,
  title: "Release this name?",
  message: "It will be available again.",
  confirmWord: "RELEASE",
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe("ConfirmDialog", () => {
  it("returns null when closed", () => {
    const { container } = render(<ConfirmDialog {...baseProps} open={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("disables confirm until typed word AND reason match", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...baseProps} onConfirm={onConfirm} />);
    const confirmBtn = screen.getByRole("button", { name: /^release$/i });
    expect(confirmBtn).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/type/i), "release");
    expect(confirmBtn).toBeDisabled(); // missing reason

    await userEvent.type(screen.getByLabelText(/reason/i), "no longer needed");
    expect(confirmBtn).not.toBeDisabled();

    await userEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledWith("no longer needed");
  });

  it("compares the typed word case-insensitively", async () => {
    render(<ConfirmDialog {...baseProps} />);
    await userEvent.type(screen.getByLabelText(/type/i), "RELEASE");
    await userEvent.type(screen.getByLabelText(/reason/i), "x");
    expect(screen.getByRole("button", { name: /^release$/i })).not.toBeDisabled();
  });

  it("calls onCancel when Cancel clicked", async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...baseProps} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("renders a busy label when busy=true", () => {
    render(<ConfirmDialog {...baseProps} busy />);
    expect(screen.getByText(/working/i)).toBeInTheDocument();
  });
});
