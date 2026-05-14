import {
  Badge,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import {
  IconActivityHeartbeat,
  IconAlertTriangle,
  IconShieldCheck,
} from "@tabler/icons-react";

import type { IngestionHealth } from "../../types/stats";

interface IngestionHealthCardProps {
  ingestionHealth: IngestionHealth;
}

/**
 * Self-healing ingestion summary card.
 *
 * Surfaces the per-log retry-budget and rate-limit state introduced by
 * Sprint 3 so operators can tell at a glance whether per-log workers are
 * making progress on their own or whether logs need manual intervention.
 */
export function IngestionHealthCard({
  ingestionHealth,
}: IngestionHealthCardProps) {
  const needsAttention = ingestionHealth.status === "attention_needed";
  const accentColor = needsAttention ? "orange" : "green";

  return (
    <Card withBorder padding="md" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" align="center">
          <Group gap="xs" align="center">
            <ThemeIcon color={accentColor} variant="light" size="md">
              {needsAttention ? (
                <IconAlertTriangle size={16} />
              ) : (
                <IconActivityHeartbeat size={16} />
              )}
            </ThemeIcon>
            <Title order={5}>Ingestion Health</Title>
          </Group>
          <StatusPill status={ingestionHealth.status} />
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
          <Stat label="Retrying" value={ingestionHealth.retrying_logs} />
          <Stat
            label="Rate-limited"
            value={ingestionHealth.rate_limited_logs}
          />
          <Stat
            label="Degraded"
            value={ingestionHealth.degraded_logs}
            highlight={ingestionHealth.degraded_logs > 0}
            highlightColor="yellow"
          />
          <Stat
            label="Paused"
            value={ingestionHealth.paused_logs}
            highlight={ingestionHealth.paused_logs > 0}
          />
        </SimpleGrid>

        <Group gap="xs" wrap="wrap">
          <Badge variant="light" color="blue">
            {ingestionHealth.retryable_error_total} retryable batch errors
          </Badge>
          <Badge variant="light" color="yellow">
            {ingestionHealth.terminal_error_total} terminal entry errors
          </Badge>
          <Badge variant="light" color="gray">
            {ingestionHealth.stale_workers} stale workers
          </Badge>
        </Group>

        <Text size="xs" c="dimmed">
          Per-log workers retry transient HTTP, parse, and database errors
          automatically. <strong>Degraded</strong> logs have hit their retry
          limit due to an external outage and will resume on their own. Only{" "}
          <strong>paused</strong> logs need operator attention.
        </Text>
      </Stack>
    </Card>
  );
}

function StatusPill({ status }: { status: IngestionHealth["status"] }) {
  if (status === "attention_needed") {
    return (
      <Badge color="orange" variant="filled" size="sm">
        attention needed
      </Badge>
    );
  }
  return (
    <Badge
      color="green"
      variant="light"
      size="sm"
      leftSection={<IconShieldCheck size={12} />}
    >
      self-healing
    </Badge>
  );
}

interface StatProps {
  label: string;
  value: number;
  highlight?: boolean;
  highlightColor?: string;
}

function Stat({
  label,
  value,
  highlight = false,
  highlightColor = "orange",
}: StatProps) {
  return (
    <Stack gap={2}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={600} c={highlight ? highlightColor : undefined}>
        {value}
      </Text>
    </Stack>
  );
}
