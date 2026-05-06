import { Box, Text } from "@mantine/core";

const APP_VERSION = import.meta.env.VITE_APP_VERSION || "dev";

/**
 * Global footer pinned to the bottom of the viewport.
 * On mobile it sits above the bottom navigation bar.
 */
export function AppFooter() {
  const year = new Date().getFullYear();
  const yearLabel = String(year);

  return (
    <Box
      component="footer"
      pos="fixed"
      left={0}
      right={0}
      bottom={{ base: 60, sm: 0 }}
      h={36}
      px="md"
      style={{
        zIndex: 180,
        borderTop: "1px solid var(--mantine-color-default-border)",
        backgroundColor: "var(--mantine-color-body)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text size="xs" c="dimmed" ta="center">
        {`Copyright \u00A9 ${yearLabel} BitsysCerts | v${APP_VERSION}`}
      </Text>
    </Box>
  );
}
