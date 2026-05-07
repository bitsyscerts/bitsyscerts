import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsPage } from "@/pages/StatsPage/StatsPage";
import { AllProviders } from "../AllProviders";

vi.mock("@/hooks/useStats", () => ({
  useStats: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
  }),
}));

vi.mock("@/hooks/useStorageSettings", () => ({
  useStorageSettings: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
  }),
}));

describe("StatsPage", () => {
  it("renders without crashing (redirects to dashboard)", () => {
    const { container } = render(
      <AllProviders initialEntries={["/stats"]}>
        <StatsPage />
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });

  it("is not a form or interactive page", () => {
    render(
      <AllProviders initialEntries={["/stats"]}>
        <StatsPage />
      </AllProviders>,
    );
    // No watch checkbox — legacy UI was removed
    expect(screen.queryByRole("checkbox", { name: /watch/i })).toBeNull();
  });
});
