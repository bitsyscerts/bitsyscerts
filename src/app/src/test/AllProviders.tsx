import type { ReactNode } from "react";
import { MantineProvider } from "@mantine/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ColorSchemeProvider } from "@/context/ColorSchemeContext";
import { SearchStateProvider } from "@/context/SearchStateContext";
import { CertStateProvider } from "@/context/CertStateContext";
import { PageProvider } from "@/context/PageContext";

interface AllProvidersProps {
  children: ReactNode;
  initialEntries?: string[];
}

// Shared client: avoids creating a new QueryClient per render (reduces per-test overhead).
const testQueryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, staleTime: 0 } },
});

/**
 * Wraps children in all providers needed for full component rendering.
 * Uses MemoryRouter so tests don't need a real browser URL.
 * MantineProvider uses default theme to minimise initialisation overhead.
 */
export function AllProviders({
  children,
  initialEntries = ["/hosts"],
}: AllProvidersProps) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <ColorSchemeProvider>
        <QueryClientProvider client={testQueryClient}>
          <MantineProvider>
            <SearchStateProvider>
              <CertStateProvider>
                <PageProvider>{children}</PageProvider>
              </CertStateProvider>
            </SearchStateProvider>
          </MantineProvider>
        </QueryClientProvider>
      </ColorSchemeProvider>
    </MemoryRouter>
  );
}
