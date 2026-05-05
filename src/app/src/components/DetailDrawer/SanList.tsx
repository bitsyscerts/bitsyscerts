import { Stack, Text, Badge, Group } from "@mantine/core";

interface SanListProps {
  sans: string[];
}

/**
 * Renders subject_alternative_names as a labeled badge list; shows a
 * placeholder when the array is empty.
 */
export function SanList({ sans }: SanListProps) {
  return (
    <Stack gap={6}>
      <Text size="sm" fw={600}>
        Subject Alternative Names ({sans.length})
      </Text>
      {sans.length === 0 ? (
        <Text size="xs" c="dimmed">
          No SANs recorded
        </Text>
      ) : (
        <Group gap={4} wrap="wrap">
          {sans.map((san) => (
            <Badge
              key={san}
              size="xs"
              variant="outline"
              color="gray"
              ff="monospace"
            >
              {san}
            </Badge>
          ))}
        </Group>
      )}
    </Stack>
  );
}
