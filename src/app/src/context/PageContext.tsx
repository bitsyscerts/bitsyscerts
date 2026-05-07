import { createContext, useContext, type ReactNode } from "react";
import { useNavigate, useLocation } from "react-router-dom";

export type ActivePage = "dashboard" | "hosts" | "certificates" | "settings";

const PAGE_ROUTES: Record<ActivePage, string> = {
  dashboard: "/",
  hosts: "/hosts",
  certificates: "/certificates",
  settings: "/settings",
};

function locationToPage(pathname: string): ActivePage {
  if (pathname.startsWith("/hosts")) return "hosts";
  if (pathname.startsWith("/certificates")) return "certificates";
  if (pathname.startsWith("/settings")) return "settings";
  return "dashboard";
}

interface PageContextValue {
  activePage: ActivePage;
  setActivePage: (page: ActivePage) => void;
}

const PageContext = createContext<PageContextValue | null>(null);

interface PageProviderProps {
  children: ReactNode;
}

/**
 * Router-backed page context. Derives activePage from the current URL and
 * navigates on setActivePage — no local state needed.
 * Must be rendered inside a react-router-dom <Router>.
 */
export function PageProvider({ children }: PageProviderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const activePage = locationToPage(location.pathname);

  function setActivePage(page: ActivePage) {
    void navigate(PAGE_ROUTES[page]);
  }

  return (
    <PageContext.Provider value={{ activePage, setActivePage }}>
      {children}
    </PageContext.Provider>
  );
}

export function usePageContext(): PageContextValue {
  const ctx = useContext(PageContext);
  if (!ctx) throw new Error("usePageContext must be used inside PageProvider");
  return ctx;
}
