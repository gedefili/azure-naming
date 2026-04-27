/*
 * Repository: azure-naming
 * Path: web/src/components/SignInScreen.test.tsx
 * Purpose: Tests for SignInScreen sign-in trigger
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const loginRedirect = vi.fn().mockResolvedValue(undefined);
vi.mock("@azure/msal-react", () => ({
  useMsal: () => ({ instance: { loginRedirect }, accounts: [] }),
}));

import { SignInScreen } from "./SignInScreen";

describe("SignInScreen", () => {
  it("triggers loginRedirect when the sign-in button is clicked", async () => {
    render(<SignInScreen />);
    await userEvent.click(screen.getByRole("button", { name: /sign in with microsoft/i }));
    expect(loginRedirect).toHaveBeenCalled();
  });
});
