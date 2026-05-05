import { Box, Text } from "@mantine/core";
import type { ReactNode } from "react";

interface DetailFieldProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
}

/**
 * Single labelled field used in detail drawer bodies.
 * Renders label above, value below with optional monospace font.
 */
export function DetailField({ label, value, mono = false }: DetailFieldProps) {
  return (
    <Box>
      <Text
        size="xs"
        c="dimmed"
        fw={500}
        tt="uppercase"
        style={{ letterSpacing: "0.04em" }}
      >
        {label}
      </Text>
      <Text
        size="sm"
        ff={mono ? "monospace" : undefined}
        style={{ wordBreak: "break-all" }}
      >
        {value ?? (
          <Text component="span" c="dimmed" size="sm">
            —
          </Text>
        )}
      </Text>
    </Box>
  );
}
