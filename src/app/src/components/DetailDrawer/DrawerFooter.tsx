import { Box, Button, Divider } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";

interface DrawerFooterProps {
  onBack: () => void;
}

/**
 * Sticky drawer footer with a single "← Back" button at the bottom-left.
 */
export function DrawerFooter({ onBack }: DrawerFooterProps) {
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
      <Box p="md" pt="xs">
        <Button
          variant="subtle"
          leftSection={<IconChevronLeft size={14} />}
          onClick={onBack}
          size="sm"
        >
          Back
        </Button>
      </Box>
    </Box>
  );
}
