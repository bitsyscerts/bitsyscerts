import { createContext, useContext, type ReactNode } from "react";
import { useSearchState, type SearchState } from "@/hooks/useSearchState";

const SearchStateContext = createContext<SearchState | null>(null);

interface SearchStateProviderProps {
  children: ReactNode;
}

/**
 * Lifts hostname search state above the router so it survives navigation
 * between pages. HostsContent reads from this context rather than creating
 * its own local state.
 */
export function SearchStateProvider({ children }: SearchStateProviderProps) {
  const state = useSearchState();
  return (
    <SearchStateContext.Provider value={state}>
      {children}
    </SearchStateContext.Provider>
  );
}

export function useSearchStateContext(): SearchState {
  const ctx = useContext(SearchStateContext);
  if (!ctx) {
    throw new Error(
      "useSearchStateContext must be used inside SearchStateProvider",
    );
  }
  return ctx;
}
