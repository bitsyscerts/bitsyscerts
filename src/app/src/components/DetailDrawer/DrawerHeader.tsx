import { Box, Divider, Group, Text } from "@mantine/core";
import type { ReactNode } from "react";

interface DrawerHeaderProps {
  icon: ReactNode;
  title: string;
  description: string;
}

/**
 * Sticky drawer header: icon + title on one line, description underneath.
 */
export function DrawerHeader({ icon, title, description }: DrawerHeaderProps) {
  return (
    <Box
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "var(--mantine-color-body)",
      }}
    >
      <Group gap="sm" p="md" pb="xs" align="flex-start" wrap="nowrap">
        <Box style={{ flexShrink: 0, marginTop: 2 }}>{icon}</Box>
        <Box style={{ minWidth: 0 }}>
          <Text fw={700} size="md" truncate>
            {title}
          </Text>
          <Text size="xs" c="dimmed" style={{ wordBreak: "break-all" }}>
            {description}
          </Text>
        </Box>
      </Group>
      <Divider />
    </Box>
  );
}
