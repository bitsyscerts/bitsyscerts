import { Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconEye, IconServer } from "@tabler/icons-react";
import { formatNumber } from "@/utils/format";
import type { SnapshotMetadata } from "@/types";

interface IndexSummaryProps {
  totalHostnames: number;
  totalCertificates: number;
  totalLogs: number;
  snapshot: SnapshotMetadata | null | undefined;
  onInspectLogs: () => void;
}

function SnapshotAge({
  snapshot,
}: {
  snapshot: SnapshotMetadata | null | undefined;
}) {
  if (!snapshot || snapshot.source === "none") {
    return (
      <Text size="xs" c="dimmed">
        No snapshot yet
      </Text>
    );
  }
  if (snapshot.is_stale) {
    return (
      <Text size="xs" c="yellow">
        Snapshot stale
      </Text>
    );
  }
  const age = snapshot.age_seconds;
  if (age == null) return null;
  const label =
    age < 60 ? `${String(age)}s ago` : `${String(Math.round(age / 60))}m ago`;
  return (
    <Text size="xs" c="dimmed">
      Snapshot {label}
    </Text>
  );
}

export function IndexSummary({
  totalHostnames,
  totalCertificates,
  totalLogs,
  snapshot,
  onInspectLogs,
}: IndexSummaryProps) {
  return (
    <Paper withBorder radius="md" p="sm">
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs">
            <IconServer size={16} />
            <Text size="sm" fw={700}>
              Index Summary
            </Text>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconEye size={14} />}
            onClick={onInspectLogs}
          >
            Inspect CT logs
          </Button>
        </Group>

        <Group gap="md" wrap="wrap">
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
              Hostnames
            </Text>
            <Text size="md" fw={700}>
              {formatNumber(totalHostnames)}
            </Text>
          </Stack>
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
              Certificates
            </Text>
            <Text size="md" fw={700}>
              {formatNumber(totalCertificates)}
            </Text>
          </Stack>
          <Stack gap={2}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
              CT Logs
            </Text>
            <Text size="md" fw={700}>
              {totalLogs}
            </Text>
          </Stack>
        </Group>

        <SnapshotAge snapshot={snapshot} />
      </Stack>
    </Paper>
  );
}
