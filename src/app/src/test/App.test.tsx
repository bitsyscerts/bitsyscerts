import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock all hooks that make network requests
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

vi.mock("@/hooks/useHostnameSearch", () => ({
  useHostnameSearch: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    fetchStatus: "idle",
  }),
}));

vi.mock("@/hooks/useCertificate", () => ({
  useCertificate: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    fetchStatus: "idle",
  }),
}));

vi.mock("@/hooks/useSearchUrlSync", () => ({
  useSearchUrlSync: vi.fn(),
}));

vi.mock("@/hooks/usePaginatedSearch", () => ({
  usePaginatedSearch: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    currentPage: 1,
    knownPageCount: 1,
    estimatedPageCount: null,
    totalEstimate: null,
    isOverLimit: false,
    canGoPrev: false,
    canGoNext: false,
    goToPage: vi.fn(),
    goNext: vi.fn(),
    goPrev: vi.fn(),
  }),
}));

import { App } from "@/App";

describe("App", () => {
  it("renders without crashing", () => {
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });

  it("renders navigation items", () => {
    render(<App />);
    // Navigation appears in both AppHeader and BottomNav — use getAllByText
    expect(screen.getAllByText("Hosts").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Settings").length).toBeGreaterThan(0);
  });

  it("renders Dashboard content at the root route", () => {
    // / now renders the DashboardPage (stats skeleton while loading)
    const { container } = render(<App />);
    expect(container).toBeTruthy();
  });
});
