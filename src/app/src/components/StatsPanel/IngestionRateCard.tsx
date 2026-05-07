import { Paper, SimpleGrid, Stack, Text, Group, Badge } from "@mantine/core";
import type { IngestionRateStats } from "@/types";
import { formatRatePerMin } from "@/utils/format";

interface IngestionRateCardProps {
  ingestionRate: IngestionRateStats;
}

interface WindowColumnProps {
  label: string;
  observationsPerSec: number;
  certsPerMin: number;
  hostnamesPerMin: number;
}

function MetricRow({ label, value }: { label: string; value: string }) {
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

function WindowColumn({
  label,
  observationsPerSec,
  certsPerMin,
  hostnamesPerMin,
}: WindowColumnProps) {
  return (
    <Stack gap="xs">
      <Text size="xs" fw={600} c="dimmed" tt="uppercase">
        {label}
      </Text>
      <MetricRow
        label="Observations/sec"
        value={observationsPerSec.toFixed(2)}
      />
      <MetricRow label="Certs/min" value={formatRatePerMin(certsPerMin)} />
      <MetricRow
        label="Hostnames/min"
        value={formatRatePerMin(hostnamesPerMin)}
      />
    </Stack>
  );
}

function windowLabel(seconds: number): string {
  if (seconds < 3600) return `${String(seconds / 60)}m`;
  return `${String(seconds / 3600)}h`;
}

/**
 * Renders a Mantine Paper card showing ingestion throughput for each time window.
 */
export function IngestionRateCard({ ingestionRate }: IngestionRateCardProps) {
  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Ingestion Rate
            </Text>
            <Text size="xs" c="dimmed">
              Throughput by rolling window
            </Text>
          </Stack>
          <Badge variant="light" color="gray">
            Live
          </Badge>
        </Group>
        <SimpleGrid cols={ingestionRate.windows.length || 1} spacing="md">
          {ingestionRate.windows.map((w) => (
            <WindowColumn
              key={w.window_seconds}
              label={windowLabel(w.window_seconds)}
              observationsPerSec={w.observations_per_sec}
              certsPerMin={w.certs_per_min}
              hostnamesPerMin={w.hostnames_per_min}
            />
          ))}
        </SimpleGrid>
      </Stack>
    </Paper>
  );
}
