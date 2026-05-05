import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AllProviders } from "../AllProviders";

// Mock usePaginatedSearch to prevent API calls
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

// Mock useSearchUrlSync to prevent infinite loop on stable state ref
vi.mock("@/hooks/useSearchUrlSync", () => ({
  useSearchUrlSync: vi.fn(),
}));

import { HostsContent } from "@/pages/SearchPage/SearchPageContent";

function renderPage() {
  return render(
    <AllProviders initialEntries={["/hosts"]}>
      <HostsContent />
    </AllProviders>,
  );
}

describe("HostsContent", () => {
  it("renders search box without crash", () => {
    const { container } = renderPage();
    expect(container).toBeTruthy();
  });

  it("renders the search input", () => {
    renderPage();
    const input = screen.getByRole("textbox", { name: /search query/i });
    expect(input).toBeInTheDocument();
  });

  it("renders the options toggle button", () => {
    renderPage();
    const btn = screen.getByRole("button", { name: /show search filters/i });
    expect(btn).toBeInTheDocument();
  });

  it("shows empty state when no results and no query submitted", () => {
    renderPage();
    // No results displayed (no query submitted yet)
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
