import {
  Alert,
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import type { TailFreshnessStats } from "@/types";
import { formatLagSeconds } from "@/utils/format";

interface TailFreshnessCardProps {
  tailFreshness: TailFreshnessStats;
}

interface DetailItemProps {
  label: string;
  value: string;
}

function DetailItem({ label, value }: DetailItemProps) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" fw={500}>
        {value}
      </Text>
    </Stack>
  );
}

function staleCountColor(count: number): string {
  if (count === 0) return "teal";
  if (count <= 2) return "yellow";
  return "red";
}

/**
 * Renders a Mantine Paper card summarising CT log tail-cursor staleness.
 */
export function TailFreshnessCard({ tailFreshness }: TailFreshnessCardProps) {
  const hasStale = tailFreshness.stale_log_count > 0;
  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Tail Freshness
            </Text>
            <Text size="xs" c="dimmed">
              Lag vs live CT logs
            </Text>
          </Stack>
          <Badge
            variant="light"
            color={staleCountColor(tailFreshness.stale_log_count)}
          >
            {tailFreshness.stale_log_count === 0
              ? "all fresh"
              : `${String(tailFreshness.stale_log_count)} stale`}
          </Badge>
        </Group>
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <DetailItem
            label="Oldest lag"
            value={formatLagSeconds(tailFreshness.oldest_lag_seconds)}
          />
          <DetailItem
            label="Median lag"
            value={formatLagSeconds(tailFreshness.median_lag_seconds)}
          />
          <DetailItem
            label="Stale threshold"
            value={formatLagSeconds(tailFreshness.stale_threshold_seconds)}
          />
          <DetailItem
            label="Stale logs"
            value={String(tailFreshness.stale_log_count)}
          />
        </SimpleGrid>
        {hasStale && (
          <Alert
            icon={<IconAlertTriangle size={16} />}
            color="yellow"
            variant="light"
          >
            {tailFreshness.stale_log_count} log
            {tailFreshness.stale_log_count === 1 ? "" : "s"} have not synced in
            over {formatLagSeconds(tailFreshness.stale_threshold_seconds)}.
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}
