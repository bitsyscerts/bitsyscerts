import { useState } from "react";
import {
  DEFAULT_HOSTNAME_SEARCH_PARAMS,
  type HostnameSearchParams,
  type SortField,
} from "@/types";

export interface SearchState {
  /** Controlled value of the text input (updates on every keystroke). */
  query: string;
  /** Last submitted query — the value actually sent to the API. */
  submittedQuery: string;
  options: Omit<HostnameSearchParams, "q" | "cursor">;
  setQuery: (query: string) => void;
  /** Commit the current query as the submitted query, triggering a search. */
  submitSearch: () => void;
  setRecursive: (value: boolean) => void;
  setDepth: (value: number | null) => void;
  setSort: (value: SortField) => void;
  setLimit: (value: number) => void;
  setIncludeCerts: (value: boolean) => void;
  resetOptions: () => void;
  /** Atomically set both the input query and the submitted query. */
  submitWithQuery: (q: string) => void;
  buildParams: (cursor?: string | null) => HostnameSearchParams;
}

const DEFAULT_OPTIONS = {
  recursive: DEFAULT_HOSTNAME_SEARCH_PARAMS.recursive,
  depth: DEFAULT_HOSTNAME_SEARCH_PARAMS.depth,
  sort: DEFAULT_HOSTNAME_SEARCH_PARAMS.sort,
  limit: DEFAULT_HOSTNAME_SEARCH_PARAMS.limit,
  include_certs: DEFAULT_HOSTNAME_SEARCH_PARAMS.include_certs,
};

/**
 * Owns hostname search form state. Separates the typed query from the
 * submitted query so API calls only fire on explicit user submit actions.
 */
export function useSearchState(): SearchState {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [options, setOptions] = useState(DEFAULT_OPTIONS);

  function submitSearch() {
    setSubmittedQuery(query);
  }

  function setRecursive(value: boolean) {
    setOptions((prev) => ({
      ...prev,
      recursive: value,
      depth: value ? prev.depth : null,
    }));
  }

  function setDepth(value: number | null) {
    setOptions((prev) => ({ ...prev, depth: value }));
  }

  function setSort(value: SortField) {
    setOptions((prev) => ({ ...prev, sort: value }));
  }

  function setLimit(value: number) {
    setOptions((prev) => ({ ...prev, limit: value }));
  }

  function setIncludeCerts(value: boolean) {
    setOptions((prev) => ({ ...prev, include_certs: value }));
  }

  function resetOptions() {
    setOptions(DEFAULT_OPTIONS);
  }

  function submitWithQuery(q: string) {
    setQuery(q);
    setSubmittedQuery(q);
  }

  function buildParams(cursor: string | null = null): HostnameSearchParams {
    return { q: submittedQuery, ...options, cursor };
  }

  return {
    query,
    submittedQuery,
    options,
    setQuery,
    submitSearch,
    setRecursive,
    setDepth,
    setSort,
    setLimit,
    setIncludeCerts,
    resetOptions,
    submitWithQuery,
    buildParams,
  };
}
