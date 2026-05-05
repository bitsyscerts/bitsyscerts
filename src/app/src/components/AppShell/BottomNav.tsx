import { Box, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import {
  IconServer,
  IconCertificate,
  IconChartBar,
  type Icon as TablerIcon,
} from "@tabler/icons-react";
import { usePageContext, type ActivePage } from "@/context/PageContext";

const NAV_ITEMS: { value: ActivePage; label: string; Icon: TablerIcon }[] = [
  { value: "hosts", label: "Hosts", Icon: IconServer },
  { value: "certificates", label: "Certificates", Icon: IconCertificate },
  { value: "stats", label: "Stats", Icon: IconChartBar },
];

/**
 * Mobile-only bottom navigation bar (hidden on sm+ breakpoints). Mirrors the
 * header tabs so navigation is always reachable with one thumb.
 */
export function BottomNav() {
  const { activePage, setActivePage } = usePageContext();

  return (
    <Box
      hiddenFrom="sm"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 200,
        height: 60,
        borderTop: "1px solid var(--mantine-color-default-border)",
        backgroundColor: "var(--mantine-color-body)",
      }}
    >
      <Group h="100%" justify="space-around" align="center" px="xs">
        {NAV_ITEMS.map(({ value, label, Icon }) => {
          const active = activePage === value;
          return (
            <UnstyledButton
              key={value}
              onClick={() => {
                setActivePage(value);
              }}
              style={{ flex: 1 }}
              aria-label={label}
              aria-current={active ? "page" : undefined}
            >
              <Stack gap={2} align="center">
                <Icon
                  size={20}
                  color={
                    active
                      ? "var(--mantine-color-brand-filled)"
                      : "var(--mantine-color-dimmed)"
                  }
                />
                <Text
                  size="xs"
                  c={active ? "brand" : "dimmed"}
                  fw={active ? 600 : 400}
                >
                  {label}
                </Text>
              </Stack>
            </UnstyledButton>
          );
        })}
      </Group>
    </Box>
  );
}
