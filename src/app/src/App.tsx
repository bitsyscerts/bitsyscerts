import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import {
  ColorSchemeProvider,
  useColorSchemeContext,
} from "./context/ColorSchemeContext";
import { PageProvider } from "./context/PageContext";
import { SearchStateProvider } from "./context/SearchStateContext";
import { CertStateProvider } from "./context/CertStateContext";
import { AppShell } from "./components/AppShell/AppShell";
import { HostsPage } from "./pages/SearchPage/SearchPage";
import { CertificatesPage } from "./pages/CertificatesPage/CertificatesPage";
import { StatsPage } from "./pages/StatsPage/StatsPage";
import { NotFoundPage } from "./pages/NotFoundPage/NotFoundPage";
import { theme } from "./theme";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

function MantineColorSchemeSync({ children }: { children: React.ReactNode }) {
  const { colorScheme } = useColorSchemeContext();
  return (
    <MantineProvider
      theme={theme}
      defaultColorScheme="auto"
      forceColorScheme={colorScheme === "system" ? undefined : colorScheme}
    >
      <Notifications />
      {children}
    </MantineProvider>
  );
}

/**
 * App root. BrowserRouter wraps everything so PageProvider (which uses
 * useNavigate/useLocation) and all route-aware hooks work correctly.
 * SearchStateProvider lives above the routes so search state survives
 * navigation between pages.
 */
export function App() {
  return (
    <BrowserRouter>
      <ColorSchemeProvider>
        <QueryClientProvider client={queryClient}>
          <MantineColorSchemeSync>
            <SearchStateProvider>
              <CertStateProvider>
                <PageProvider>
                  <AppShell>
                    <Routes>
                      <Route
                        path="/"
                        element={<Navigate to="/hosts" replace />}
                      />
                      <Route path="/hosts" element={<HostsPage />} />
                      <Route
                        path="/certificates"
                        element={<CertificatesPage />}
                      />
                      <Route path="/stats" element={<StatsPage />} />
                      <Route path="*" element={<NotFoundPage />} />
                    </Routes>
                  </AppShell>
                </PageProvider>{" "}
              </CertStateProvider>{" "}
            </SearchStateProvider>
          </MantineColorSchemeSync>
        </QueryClientProvider>
      </ColorSchemeProvider>
    </BrowserRouter>
  );
}
