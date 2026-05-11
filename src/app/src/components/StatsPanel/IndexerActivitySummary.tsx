import { Badge, Button, Group, Paper, Stack, Text } from "@mantine/core";
import { IconEye, IconUsers } from "@tabler/icons-react";
import { formatRatePerMin } from "@/utils/format";
import type { IngestionRateStats, IngestionRateWindow, WorkerSummary } from "@/types";

interface IndexerActivitySummaryProps {
  workers: WorkerSummary | null;
  ingestionRate: IngestionRateStats;
  onInspectWorkers: () => void;
}

function shortestWindow(
  rate: IngestionRateStats,
): IngestionRateWindow | null {
  const sorted = [...rate.windows].sort(
    (a, b) => a.window_seconds - b.window_seconds,
  );
  return sorted[0] ?? null;
}

export function IndexerActivitySummary({
  workers,
  ingestionRate,
  onInspectWorkers,
}: IndexerActivitySummaryProps) {
  const window = shortestWindow(ingestionRate);
  const obsPerMin =
    window != null
      ? (window.observations_per_min ?? window.observations_per_sec * 60)
      : null;

  return (
    <Paper withBorder radius="md" p="sm">
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs">
            <IconUsers size={16} />
            <Text size="sm" fw={700}>
              Indexer Activity
            </Text>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconEye size={14} />}
            onClick={onInspectWorkers}
          >
            Inspect workers
          </Button>
        </Group>

        <Group gap="md" wrap="wrap">
          {workers ? (
            <>
              <Stack gap={2}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                  Active
                </Text>
                <Text size="md" fw={700}>
                  {workers.active_total}
                </Text>
              </Stack>
              {workers.stale_total > 0 && (
                <Badge color="red" variant="light" size="sm">
                  {workers.stale_total} stale
                </Badge>
              )}
              <Stack gap={2}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                  Tail / Backfill
                </Text>
                <Text size="md" fw={700}>
                  {workers.tail_active} / {workers.backfill_active}
                </Text>
              </Stack>
            </>
          ) : (
            <Text size="sm" c="dimmed">
              No worker data
            </Text>
          )}
          {obsPerMin !== null && (
            <Stack gap={2}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                Rate
              </Text>
              <Text size="md" fw={700}>
                {formatRatePerMin(obsPerMin)} obs/min
              </Text>
            </Stack>
          )}
        </Group>
      </Stack>
    </Paper>
  );
}
