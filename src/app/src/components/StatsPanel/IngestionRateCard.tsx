import { Paper, SimpleGrid, Stack, Text, Group, Badge } from "@mantine/core";
import type { IngestionRateStats, IngestionRateWindow } from "@/types";
import { formatRatePerMin } from "@/utils/format";

interface IngestionRateCardProps {
  ingestionRate: IngestionRateStats;
}

interface WindowColumnProps {
  label: string;
  window: IngestionRateWindow;
}

function MetricRow({ label, value }: { label: string; value: string | null }) {
  if (value === null) return null;
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

function optionalRate(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  return formatRatePerMin(value);
}

function WindowColumn({ label, window: w }: WindowColumnProps) {
  // Sprint 5: precise labels.  Throughput first, then uniqueness, then
  // errors.  Optional fields hide themselves when the producer has not
  // populated them yet (no zero-noise).
  const obsPerMin = w.observations_per_min ?? w.observations_per_sec * 60;
  return (
    <Stack gap="xs">
      <Text size="xs" fw={600} c="dimmed" tt="uppercase">
        {label}
      </Text>
      <Text size="xs" fw={600} c="dimmed">
        Throughput
      </Text>
      <MetricRow label="Observations/min" value={formatRatePerMin(obsPerMin)} />
      <MetricRow
        label="Certs parsed/min"
        value={formatRatePerMin(
          w.certificates_parsed_per_min ?? w.certs_per_min,
        )}
      />
      <MetricRow
        label="Hostnames observed/min"
        value={formatRatePerMin(
          w.hostnames_observed_per_min ?? w.hostnames_per_min,
        )}
      />

      <Text size="xs" fw={600} c="dimmed">
        Uniqueness
      </Text>
      <MetricRow
        label="New certs/min"
        value={optionalRate(w.new_unique_certificates_per_min)}
      />
      <MetricRow
        label="Duplicate certs/min"
        value={optionalRate(w.duplicate_certificates_per_min)}
      />
      <MetricRow
        label="New hostnames/min"
        value={optionalRate(w.new_unique_hostnames_per_min)}
      />
      <MetricRow
        label="Known hostnames/min"
        value={optionalRate(w.known_hostnames_per_min)}
      />

      <Text size="xs" fw={600} c="dimmed">
        Errors
      </Text>
      <MetricRow
        label="Retryable errors/min"
        value={optionalRate(w.retryable_errors_per_min)}
      />
      <MetricRow
        label="Terminal entry errors/min"
        value={optionalRate(w.terminal_entry_errors_per_min)}
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
 *
 * Sprint 5: Uses precise per-metric labels so the operator can tell
 * "observations" from "certificates parsed" from "new unique certificates",
 * and the same for hostnames.  Uniqueness and error fields are optional —
 * when the producer has not populated them, the rows are hidden rather
 * than displaying zero.
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
              Throughput, uniqueness, and errors by rolling window
            </Text>
            <Text size="xs" c="dimmed">
              Duplicate rates reflect overlap across CT logs and repeated
              certificate observations. High duplicate throughput is normal once
              the index has warmed up.
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
              window={w}
            />
          ))}
        </SimpleGrid>
      </Stack>
    </Paper>
  );
}
