import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { useSearchUrlSync } from "@/hooks/useSearchUrlSync";
import type { SearchState } from "@/hooks/useSearchState";

const NOOP = vi.fn();

function makeSearch(overrides: Partial<SearchState> = {}): SearchState {
  return {
    query: "",
    submittedQuery: "",
    options: {
      recursive: true,
      depth: null,
      sort: "not_before_desc",
      limit: 50,
      include_certs: false,
    },
    setQuery: NOOP,
    setRecursive: NOOP,
    setDepth: NOOP,
    setSort: NOOP,
    setLimit: NOOP,
    setIncludeCerts: NOOP,
    submitWithQuery: NOOP,
    submitSearch: NOOP,
    resetOptions: NOOP,
    buildParams: () => ({
      q: "",
      recursive: true,
      depth: null,
      sort: "not_before_desc",
      limit: 50,
      cursor: null,
      include_certs: false,
    }),
    ...overrides,
  };
}

describe("useSearchUrlSync", () => {
  it("does not throw when mounted with empty state", () => {
    const state = makeSearch();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={["/hosts"]}>{children}</MemoryRouter>
    );
    expect(() => {
      renderHook(
        () => {
          useSearchUrlSync(state);
        },
        { wrapper },
      );
    }).not.toThrow();
  });

  it("does not throw when URL has a q param", () => {
    const state = makeSearch();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={["/hosts?q=example.com"]}>
        {children}
      </MemoryRouter>
    );
    expect(() => {
      renderHook(
        () => {
          useSearchUrlSync(state);
        },
        { wrapper },
      );
    }).not.toThrow();
  });

  it("does not throw when mounted with existing submittedQuery", () => {
    // State object must be stable across renders; creating inside the callback
    // would produce a new options reference each render and cause an infinite loop.
    const state = makeSearch({ submittedQuery: "example.com" });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={["/hosts"]}>{children}</MemoryRouter>
    );
    expect(() => {
      renderHook(
        () => {
          useSearchUrlSync(state);
        },
        { wrapper },
      );
    }).not.toThrow();
  });
});
