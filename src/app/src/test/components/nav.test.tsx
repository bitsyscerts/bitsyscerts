import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider, AppShell as MantineAppShell } from "@mantine/core";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { AllProviders } from "../AllProviders";
import { AppHeader } from "@/components/AppShell/AppHeader";
import { BottomNav } from "@/components/AppShell/BottomNav";
import { AppShell } from "@/components/AppShell/AppShell";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { ColorSchemeProvider } from "@/context/ColorSchemeContext";
import { PageProvider } from "@/context/PageContext";

// AppHeader uses MantineAppShell.Header which requires an AppShell context
function AppShellWrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <ColorSchemeProvider>
        <MantineProvider>
          <PageProvider>
            <MantineAppShell header={{ height: 60 }}>
              {children}
            </MantineAppShell>
          </PageProvider>
        </MantineProvider>
      </ColorSchemeProvider>
    </MemoryRouter>
  );
}

describe("navigation components smoke tests", () => {
  it("renders AppHeader without crash", () => {
    const { container } = render(
      <AppShellWrapper>
        <AppHeader />
      </AppShellWrapper>,
    );
    expect(container).toBeTruthy();
  });

  it("renders BottomNav without crash", () => {
    const { container } = render(
      <AllProviders>
        <BottomNav />
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });

  it("renders AppShell with children", () => {
    const { container } = render(
      <AllProviders>
        <AppShell>
          <div>content</div>
        </AppShell>
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });

  it("renders sticky footer with year and version", () => {
    render(
      <AllProviders>
        <AppShell>
          <div>content</div>
        </AppShell>
      </AllProviders>,
    );
    const year = new Date().getFullYear();
    const yearLabel = String(year);
    expect(
      screen.getByText(
        new RegExp(`Copyright\\s+\\u00A9\\s+${yearLabel}\\s+BitsysCerts`),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/\|\s+vdev$/)).toBeInTheDocument();
  });

  it("renders ThemeToggle without crash", () => {
    const { container } = render(
      <AllProviders>
        <ThemeToggle />
      </AllProviders>,
    );
    expect(container).toBeTruthy();
  });

  it("AppHeader shows nav items", () => {
    const { getByText } = render(
      <AppShellWrapper>
        <AppHeader />
      </AppShellWrapper>,
    );
    expect(getByText("Hosts")).toBeInTheDocument();
    expect(getByText("Settings")).toBeInTheDocument();
  });

  it("BottomNav shows nav items", () => {
    const { getByLabelText } = render(
      <AllProviders>
        <BottomNav />
      </AllProviders>,
    );
    expect(getByLabelText("Hosts")).toBeInTheDocument();
    expect(getByLabelText("Certificates")).toBeInTheDocument();
    expect(getByLabelText("Settings")).toBeInTheDocument();
  });
});
