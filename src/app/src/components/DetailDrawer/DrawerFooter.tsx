import { Box, Button, Divider, Group } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";
import type { ReactNode } from "react";

interface DrawerFooterProps {
  onBack: () => void;
  rightSection?: ReactNode;
}

/**
 * Sticky drawer footer with "← Back" on the left and an optional action on
 * the right (e.g. a save button).
 */
export function DrawerFooter({ onBack, rightSection }: DrawerFooterProps) {
  return (
    <Box
      style={{
        position: "sticky",
        bottom: 0,
        zIndex: 10,
        background: "var(--mantine-color-body)",
      }}
    >
      <Divider />
      <Group p="md" pt="xs" justify="space-between">
        <Button
          variant="subtle"
          leftSection={<IconChevronLeft size={14} />}
          onClick={onBack}
          size="sm"
        >
          Back
        </Button>
        {rightSection}
      </Group>
    </Box>
  );
}
