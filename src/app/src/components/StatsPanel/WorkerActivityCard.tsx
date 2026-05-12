import {
  Badge,
  Group,
  Paper,
  ScrollArea,
  SimpleGrid,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import type { WorkerSummary, WorkerSummaryItem } from "@/types";
import {
  formatWorkerActivity,
  formatWorkerAge,
  formatWorkerError,
  formatWorkerLog,
  formatWorkerLogMeta,
  formatWorkerWork,
  workerKindColor,
  workerStatusColor,
} from "./workerActivityFormat";

interface WorkerActivityCardProps {
  workers: WorkerSummary;
}

interface WorkerRowProps {
  item: WorkerSummaryItem;
}

interface SummaryStatProps {
  label: string;
  value: number;
  color: string;
}

function SummaryStat({ label, value, color }: SummaryStatProps) {
  return (
    <Paper withBorder radius="md" p="sm">
      <Stack gap={2}>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          {label}
        </Text>
        <Text size="lg" fw={700} c={color}>
          {value}
        </Text>
      </Stack>
    </Paper>
  );
}

function WorkerRow({ item }: WorkerRowProps) {
  const color = workerStatusColor(item);
  const logMeta = formatWorkerLogMeta(item);
  const errorText = formatWorkerError(item);

  return (
    <Table.Tr>
      <Table.Td>
        <Stack gap={4}>
          <Text size="xs" ff="monospace" fw={600} truncate="end" maw={200}>
            {item.worker_id}
          </Text>
          <Badge
            size="xs"
            variant="light"
            color={workerKindColor(item.worker_kind)}
            w="fit-content"
          >
            {item.worker_kind}
          </Badge>
        </Stack>
      </Table.Td>
      <Table.Td>
        <Stack gap={2}>
          <Text size="xs" fw={600} truncate="end" maw={240}>
            {formatWorkerLog(item)}
          </Text>
          {logMeta && (
            <Text size="xs" c="dimmed" truncate="end" maw={240}>
              {logMeta}
            </Text>
          )}
        </Stack>
      </Table.Td>
      <Table.Td>
        <Stack gap={4}>
          <Badge size="xs" variant="light" color={color} w="fit-content">
            {item.is_stale ? "stale" : item.status}
          </Badge>
          <Text size="xs" c="dimmed">
            {formatWorkerWork(item)}
          </Text>
        </Stack>
      </Table.Td>
      <Table.Td>
        <Stack gap={2}>
          <Text size="xs">{formatWorkerActivity(item)}</Text>
          {errorText !== "No recent errors" && (
            <Text size="xs" c={color === "red" ? "red" : "yellow.8"}>
              {errorText}
            </Text>
          )}
        </Stack>
      </Table.Td>
      <Table.Td>
        <Text size="xs" c={item.is_stale ? "red" : undefined}>
          {formatWorkerAge(item.last_heartbeat_age_seconds)}
        </Text>
      </Table.Td>
    </Table.Tr>
  );
}

/** Renders a wide worker-activity card with summary stats and live rows. */
export function WorkerActivityCard({ workers }: WorkerActivityCardProps) {
  const staleCount = workers.stale_total;
  const serviceTotal =
    workers.stats_active + workers.maintenance_active + workers.unknown_active;

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={700}>
              Worker Activity
            </Text>
            <Text size="xs" c="dimmed">
              Live worker visibility after the top totals: assignment, current
              work, freshness, and the last failure signal.
            </Text>
          </Stack>
          {staleCount > 0 ? (
            <Badge variant="light" color="red">
              {staleCount} stale
            </Badge>
          ) : (
            <Badge variant="light" color="green">
              all fresh
            </Badge>
          )}
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 5 }}>
          <SummaryStat label="Healthy" value={workers.active_total} color="green" />
          <SummaryStat label="Stale" value={workers.stale_total} color="red" />
          <SummaryStat label="Tail" value={workers.tail_active} color="blue" />
          <SummaryStat
            label="Backfill"
            value={workers.backfill_active}
            color="grape"
          />
          <SummaryStat label="Services" value={serviceTotal} color="teal" />
        </SimpleGrid>

        <Group gap="xs">
          <Badge variant="light" color="teal">
            snapshot {workers.stats_active}
          </Badge>
          <Badge variant="light" color="orange">
            maintenance {workers.maintenance_active}
          </Badge>
          {workers.unknown_active > 0 && (
            <Badge variant="light" color="gray">
              unknown {workers.unknown_active}
            </Badge>
          )}
        </Group>

        {workers.items.length === 0 ? (
          <Text size="xs" c="dimmed">
            No active workers right now.
          </Text>
        ) : (
          <ScrollArea>
            <Table highlightOnHover withTableBorder={false} fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Worker</Table.Th>
                  <Table.Th>Assignment</Table.Th>
                  <Table.Th>State</Table.Th>
                  <Table.Th>Activity</Table.Th>
                  <Table.Th>Last Seen</Table.Th>
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
