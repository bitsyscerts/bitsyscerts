import {
  Badge,
  Group,
  Paper,
  ScrollArea,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import type { WorkerSummary, WorkerSummaryItem } from "@/types";

interface WorkerActivityCardProps {
  workers: WorkerSummary;
}

interface WorkerRowProps {
  item: WorkerSummaryItem;
}

function statusColor(item: WorkerSummaryItem): string {
  if (item.is_stale) return "red";
  if (item.status === "processing") return "teal";
  if (item.status === "idle") return "blue";
  return "gray";
}

function WorkerRow({ item }: WorkerRowProps) {
  const color = statusColor(item);
  const ageStr = `${String(item.last_heartbeat_age_seconds)}s ago`;
  const indexStr =
    item.current_index != null ? item.current_index.toLocaleString() : "-";
  const logLabel = item.log_name ?? item.log_source_id ?? "-";
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="xs" ff="monospace" truncate="end" maw={160}>
          {item.worker_id}
        </Text>
      </Table.Td>
      <Table.Td>
        <Badge
          size="xs"
          variant="light"
          color={item.worker_kind === "tail" ? "blue" : "violet"}
        >
          {item.worker_kind}
        </Badge>
      </Table.Td>
      <Table.Td>
        <Text size="xs" truncate="end" maw={180}>
          {logLabel}
        </Text>
      </Table.Td>
      <Table.Td>
        <Badge size="xs" variant="light" color={color}>
          {item.is_stale ? "stale" : item.status}
        </Badge>
      </Table.Td>
      <Table.Td>
        <Text size="xs" c={item.is_stale ? "red" : undefined}>
          {ageStr}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="xs" ff="monospace">
          {indexStr}
        </Text>
      </Table.Td>
    </Table.Tr>
  );
}

/**
 * Renders a Mantine Paper card with a scrollable table of active workers
 * from ct_worker_runtime. Stale workers are highlighted in red.
 */
export function WorkerActivityCard({ workers }: WorkerActivityCardProps) {
  const staleCount = workers.stale_total;
  const activeCount = workers.active_total;

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Worker Activity
            </Text>
            <Text size="xs" c="dimmed">
              {activeCount} active · {workers.tail_active} tail ·{" "}
              {workers.backfill_active} backfill
            </Text>
          </Stack>
          {staleCount > 0 ? (
            <Badge variant="light" color="red">
              {staleCount} stale
            </Badge>
          ) : (
            <Badge variant="light" color="teal">
              all fresh
            </Badge>
          )}
        </Group>
        {workers.items.length === 0 ? (
          <Text size="xs" c="dimmed">
            No active workers.
          </Text>
        ) : (
          <ScrollArea>
            <Table striped highlightOnHover withTableBorder={false} fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Worker ID</Table.Th>
                  <Table.Th>Kind</Table.Th>
                  <Table.Th>Log</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Last Seen</Table.Th>
                  <Table.Th>Index</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {workers.items.map((item) => (
                  <WorkerRow key={item.worker_id} item={item} />
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Stack>
    </Paper>
  );
}
