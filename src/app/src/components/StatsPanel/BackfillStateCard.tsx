import {
  Badge,
  Group,
  Paper,
  Progress,
  ScrollArea,
  Stack,
  Table,
  Text,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { BackfillStateItem, BackfillStateSummary } from "@/types";

interface BackfillStateCardProps {
  state: BackfillStateSummary;
}

interface BackfillStateRowProps {
  item: BackfillStateItem;
}

function statusColor(item: BackfillStateItem): string {
  if (item.is_stale) return "red";
  if (item.status === "complete") return "teal";
  if (item.status === "processing" || item.status === "claimed") return "blue";
  if (item.status === "retrying" || item.status === "error") return "orange";
  if (item.status === "paused") return "yellow";
  return "gray";
}

function formatIndex(value: number | null): string {
  if (value === null) return "-";
  return value.toLocaleString();
}

function formatProgress(value: number | null): string {
  if (value === null) return "-";
  return `${value.toFixed(1)}%`;
}

function formatErrorAt(at: string | null | undefined): string {
  if (!at) return "";
  return ` — ${new Date(at).toLocaleString()}`;
}

function BackfillStateRow({ item }: BackfillStateRowProps) {
  const color = statusColor(item);
  const label = item.log_name ?? item.log_source_id;
  const checkpoint = formatIndex(item.checkpoint_index);
  const window =
    item.backfill_start_index === null && item.backfill_end_index === null
      ? "-"
      : `${formatIndex(item.backfill_start_index)} → ${formatIndex(item.backfill_end_index)}`;

  const DETAIL_STATUSES = new Set(["paused", "retrying", "error"]);
  const hasPauseDetail =
    DETAIL_STATUSES.has(item.status) &&
    (item.last_error_message != null || item.last_error_type != null);
  const errorLabel = [
    item.last_error_type ? `[${item.last_error_type}]` : null,
    item.last_error_message ?? "No error message recorded.",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <Table.Tr>
        <Table.Td>
          <Text size="xs" truncate="end" maw={200}>
            {label}
          </Text>
        </Table.Td>
        <Table.Td>
          <Badge size="xs" variant="light" color={color}>
            {item.is_stale ? "stale" : item.status}
          </Badge>
        </Table.Td>
        <Table.Td>
          <Text size="xs" ff="monospace" truncate="end" maw={140}>
            {item.claimed_by ?? "-"}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="xs" ff="monospace">
            {checkpoint}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="xs" ff="monospace">
            {window}
          </Text>
        </Table.Td>
        <Table.Td>
          <Stack gap={2}>
            <Text size="xs">{formatProgress(item.progress_percent)}</Text>
            {item.progress_percent !== null ? (
              <Progress value={item.progress_percent} size="xs" color={color} />
            ) : null}
          </Stack>
        </Table.Td>
      </Table.Tr>
      {hasPauseDetail && (
        <Table.Tr>
          <Table.Td
            colSpan={6}
            py={4}
            px="md"
            bg="var(--mantine-color-red-light)"
          >
            <Group gap="xs" wrap="nowrap" align="flex-start">
              <IconAlertTriangle
                size={12}
                color="var(--mantine-color-red-filled)"
                style={{ flexShrink: 0, marginTop: 2 }}
              />
              <Text
                size="xs"
                c="red.4"
                ff="monospace"
                style={{ wordBreak: "break-all" }}
              >
                {errorLabel}
                {formatErrorAt(item.last_error_at)}
              </Text>
            </Group>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  );
}

/**
 * Renders a Mantine Paper card with the per-log backfill state table.
 *
 * Each row corresponds to one CT log row in ct_log_backfill_state, showing
 * the active dispatch model: status, current claim, checkpoint, window
 * bounds, and progress.
 */
export function BackfillStateCard({ state }: BackfillStateCardProps) {
  const completeCount = state.complete;
  const processingCount = state.processing + state.claimed;
  const retryingCount = state.retrying + state.error;
  const staleCount = state.stale;

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Per-Log Backfill State
            </Text>
            <Text size="xs" c="dimmed">
              {state.total_logs} logs · {processingCount} processing ·{" "}
              {completeCount} complete · {retryingCount} retrying
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
        {state.items.length === 0 ? (
          <Text size="xs" c="dimmed">
            No backfill state rows yet.
          </Text>
        ) : (
          <ScrollArea>
            <Table striped highlightOnHover withTableBorder={false} fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Log</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Claimed By</Table.Th>
                  <Table.Th>Checkpoint</Table.Th>
                  <Table.Th>Window</Table.Th>
                  <Table.Th>Progress</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {state.items.map((item) => (
                  <BackfillStateRow key={item.log_source_id} item={item} />
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}
      </Stack>
    </Paper>
  );
}
