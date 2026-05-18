import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import type { SearchState } from "@/hooks/useSearchState";
import type { SortField } from "@/types";

const VALID_SORT: ReadonlySet<string> = new Set([
  "not_before_asc",
  "not_before_desc",
  "not_after_asc",
  "not_after_desc",
]);

function parseSortField(raw: string | null, fallback: SortField): SortField {
  return raw && VALID_SORT.has(raw) ? (raw as SortField) : fallback;
}

function toUrlParams(search: SearchState): Record<string, string> {
  const { submittedQuery: q, options: o } = search;
  const params: Record<string, string> = {
    q,
    recursive: String(o.recursive),
    sort: o.sort,
    limit: String(o.limit),
  };
  if (o.depth != null) params.depth = String(o.depth);
  if (o.include_certs) params.include_certs = "true";
  return params;
}

/**
 * Syncs hostname search state to/from the browser URL query string so that
 * searches are bookmarkable and shareable.
 *
 * - On mount: if the URL has a `q` param, restores all search options and
 *   submits the search. If state already has a query (navigated away and
 *   back), re-writes the URL from current state.
 * - After any submit or option change: replaces the URL params in-place
 *   (no extra history entry).
 */
export function useSearchUrlSync(search: SearchState) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Capture initial values in refs so the mount effect has no deps.
  const initialParamsRef = useRef(searchParams);
  const searchRef = useRef(search);
  // Keep searchRef current on every render so URL-sync effect sees latest state.
  // eslint-disable-next-line react-hooks/refs
  searchRef.current = search;

  const didInit = useRef(false);

  // Mount-only: restore state from URL, or re-write URL from state.
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    const params = initialParamsRef.current;
    const q = params.get("q");
    const s = searchRef.current;

    if (q) {
      s.setRecursive(params.get("recursive") !== "false");
      const depthStr = params.get("depth");
      s.setDepth(depthStr ? Number(depthStr) : null);
      s.setSort(parseSortField(params.get("sort"), s.options.sort));
      const limitStr = params.get("limit");
      s.setLimit(
        limitStr
          ? Math.min(200, Math.max(1, Number(limitStr)))
          : s.options.limit,
      );
      s.setIncludeCerts(params.get("include_certs") === "true");
      s.submitWithQuery(q);
    } else if (s.submittedQuery) {
      // User navigated away and back — restore URL from in-memory state.
      setSearchParams(toUrlParams(s), { replace: true });
    }
  }, [setSearchParams]); // setSearchParams is stable; guard prevents re-init

  // State → URL: fire when submitted query or options change.
  const { submittedQuery, options } = search;
  useEffect(() => {
    if (!didInit.current || !submittedQuery) return;
    setSearchParams(toUrlParams(searchRef.current), { replace: true });
  }, [submittedQuery, options, setSearchParams]);
}
