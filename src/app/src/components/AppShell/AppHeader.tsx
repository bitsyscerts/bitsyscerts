import {
  AppShell as MantineAppShell,
  Box,
  Container,
  Group,
  Tabs,
} from "@mantine/core";
import { IconServer, IconCertificate, IconChartBar } from "@tabler/icons-react";
import { Logo } from "@/components/Logo/Logo";
import { ThemeToggle } from "@/components/ThemeToggle/ThemeToggle";
import { usePageContext, type ActivePage } from "@/context/PageContext";

const NAV_ITEMS: { value: ActivePage; label: string; icon: React.ReactNode }[] =
  [
    { value: "hosts", label: "Hosts", icon: <IconServer size={15} /> },
    {
      value: "certificates",
      label: "Certificates",
      icon: <IconCertificate size={15} />,
    },
    { value: "stats", label: "Stats", icon: <IconChartBar size={15} /> },
  ];

/**
 * Full-width application header: Logo on the left, navigation tabs in the
 * centre, ThemeToggle on the right.
 */
export function AppHeader() {
  const { activePage, setActivePage } = usePageContext();

  return (
    <MantineAppShell.Header>
      <Container size="xl" h="100%" px="md">
        <Group h="100%" justify="space-between" align="center" wrap="nowrap">
          <Logo />
          <Box visibleFrom="sm" style={{ flex: 1 }}>
            <Tabs
              value={activePage}
              onChange={(v) => setActivePage(v as ActivePage)}
              variant="pills"
            >
              <Tabs.List justify="center" style={{ flexWrap: "nowrap" }}>
                {NAV_ITEMS.map(({ value, label, icon }) => (
                  <Tabs.Tab key={value} value={value} leftSection={icon}>
                    {label}
                  </Tabs.Tab>
                ))}
              </Tabs.List>
            </Tabs>
          </Box>
          <ThemeToggle />
        </Group>
      </Container>
    </MantineAppShell.Header>
  );
}
