import { Badge, Group, Progress, Stack, Text } from "@mantine/core";
import type { LogStatsItem } from "@/types";
import { formatDate, formatNumber, formatPct } from "@/utils/format";

interface LogStatsListProps {
  logs: LogStatsItem[];
}

const STATE_COLOR: Record<string, string> = {
  active: "green",
  inactive: "gray",
  retired: "red",
  pending: "yellow",
};

/**
 * Renders each CT log as a compact summary row: description, state badge,
 * tail position, backfill progress, and last sync time.
 */
export function LogStatsList({ logs }: LogStatsListProps) {
  return (
    <Stack gap="sm">
      {logs.map((log) => (
        <Stack
          key={log.log_id}
          gap={4}
          p="xs"
          style={{ borderRadius: "var(--mantine-radius-sm)" }}
        >
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm" fw={500} truncate>
              {log.description || log.url}
            </Text>
            <Badge size="xs" color={STATE_COLOR[log.log_state] ?? "gray"}>
              {log.log_state}
            </Badge>
          </Group>
          {log.tail_position !== null && (
            <Text size="xs" c="dimmed">
              Tail position: {formatNumber(log.tail_position)}
            </Text>
          )}
          {log.backfill_complete_pct !== null && (
            <Stack gap={2}>
              <Text size="xs" c="dimmed">
                Backfill: {formatPct(log.backfill_complete_pct)}
              </Text>
              <Progress
                value={log.backfill_complete_pct ?? 0}
                size="xs"
                radius="xl"
                color="brand"
              />
            </Stack>
          )}
          {log.last_tail_sync && (
            <Text size="xs" c="dimmed">
              Last sync: {formatDate(log.last_tail_sync)}
            </Text>
          )}
        </Stack>
      ))}
    </Stack>
  );
}
