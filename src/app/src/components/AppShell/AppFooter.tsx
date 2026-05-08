import { useState } from "react";
import { Box, Text, UnstyledButton } from "@mantine/core";
import { AboutModal } from "./AboutModal";

const APP_VERSION = import.meta.env.VITE_APP_VERSION || "dev";

/**
 * Global footer pinned to the bottom of the viewport.
 * On mobile it sits above the bottom navigation bar.
 * Clicking the version string opens the About modal.
 */
export function AppFooter() {
  const [aboutOpen, setAboutOpen] = useState(false);
  const year = new Date().getFullYear();
  const yearLabel = String(year);

  return (
    <>
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
          {`Copyright \u00A9 ${yearLabel} BitsysCerts | `}
          <UnstyledButton
            onClick={() => {
              setAboutOpen(true);
            }}
            style={{
              color: "var(--mantine-color-dimmed)",
              fontSize: "var(--mantine-font-size-xs)",
              textDecoration: "underline",
              verticalAlign: "baseline",
            }}
          >
            {`v${APP_VERSION}`}
          </UnstyledButton>
        </Text>
      </Box>
      <AboutModal
        version={APP_VERSION}
        opened={aboutOpen}
        onClose={() => {
          setAboutOpen(false);
        }}
      />
    </>
  );
}
