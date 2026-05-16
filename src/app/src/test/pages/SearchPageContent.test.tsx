import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AllProviders } from "../AllProviders";
import { ApiTimeoutError } from "@/services/apiClient";

// Mock usePaginatedSearch to prevent API calls
vi.mock("@/hooks/usePaginatedSearch", () => ({
  usePaginatedSearch: vi.fn().mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
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

// Mock useSearchStateContext for error-state tests.
// Use importActual to preserve SearchStateProvider used by AllProviders.
vi.mock("@/context/SearchStateContext", async (importActual) => {
  const actual =
    await importActual<typeof import("@/context/SearchStateContext")>();
  return {
    ...actual,
    useSearchStateContext: vi.fn().mockReturnValue({
      query: "",
      submittedQuery: "",
      options: {
        recursive: false,
        depth: 1,
        sort: "not_before_desc",
        limit: 20,
        include_certs: false,
      },
      setQuery: vi.fn(),
      submitWithQuery: vi.fn(),
      submitSearch: vi.fn(),
      resetOptions: vi.fn(),
      setRecursive: vi.fn(),
      setDepth: vi.fn(),
      setSort: vi.fn(),
      setLimit: vi.fn(),
      setIncludeCerts: vi.fn(),
      buildParams: vi.fn().mockReturnValue({ q: "", limit: 20, cursor: null }),
    }),
  };
});

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

import { usePaginatedSearch } from "@/hooks/usePaginatedSearch";
import { useSearchStateContext } from "@/context/SearchStateContext";

const mockUsePaginatedSearch = vi.mocked(usePaginatedSearch);
const mockUseSearchStateContext = vi.mocked(useSearchStateContext);

const BASE_ERROR_STATE = {
  query: "example.com",
  submittedQuery: "example.com",
  options: {
    recursive: false,
    depth: 1,
    sort: "not_before_desc" as const,
    limit: 20,
    include_certs: false,
  },
  setQuery: vi.fn(),
  submitWithQuery: vi.fn(),
  submitSearch: vi.fn(),
  resetOptions: vi.fn(),
  setRecursive: vi.fn(),
  setDepth: vi.fn(),
  setSort: vi.fn(),
  setLimit: vi.fn(),
  setIncludeCerts: vi.fn(),
  buildParams: vi
    .fn()
    .mockReturnValue({ q: "example.com", limit: 20, cursor: null }),
};

function renderPageWithError(error: Error) {
  mockUseSearchStateContext.mockReturnValueOnce(BASE_ERROR_STATE);
  mockUsePaginatedSearch.mockReturnValueOnce({
    data: undefined,
    isLoading: false,
    isError: true,
    error,
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
  });

  return render(
    <AllProviders initialEntries={["/hosts"]}>
      <HostsContent />
    </AllProviders>,
  );
}

describe("HostsContent error states", () => {
  it("shows timeout alert when ApiTimeoutError is thrown", () => {
    renderPageWithError(new ApiTimeoutError());
    expect(
      screen.getByText(/search timed out — try a more specific query/i),
    ).toBeInTheDocument();
  });

  it("shows generic error alert for non-timeout errors", () => {
    renderPageWithError(new Error("Network failure"));
    expect(screen.getByText(/unexpected error occurred/i)).toBeInTheDocument();
  });
});
