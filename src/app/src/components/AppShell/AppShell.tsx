import { AppShell as MantineAppShell, Box } from "@mantine/core";
import type { ReactNode } from "react";
import { AppHeader } from "./AppHeader";
import { AppFooter } from "./AppFooter";
import { BottomNav } from "./BottomNav";

interface AppShellProps {
  children: ReactNode;
}

/**
 * Mantine AppShell wrapper with the site header; renders children in the
 * full-width main content area.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <MantineAppShell header={{ height: 60 }} padding="md">
      <AppHeader />
      <MantineAppShell.Main>
        {/* pb prevents content hiding behind sticky footer + mobile bottom nav */}
        <Box pb={{ base: 104, sm: 44 }}>{children}</Box>
      </MantineAppShell.Main>
      <AppFooter />
      <BottomNav />
    </MantineAppShell>
  );
}
