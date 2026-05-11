import { Group, Paper, Progress, SimpleGrid, Stack, Text } from "@mantine/core";
import type { HostCapacityStats } from "@/types";
import { formatStorageSize } from "@/utils/format";

interface HostCapacityCardProps {
  capacity: HostCapacityStats;
}

interface GaugeRowProps {
  label: string;
  value: number | null;
  used: number | null;
  total: number | null;
}

interface StatRowProps {
  label: string;
  value: string;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
        {label}
      </Text>
      <Text size="xs" fw={500} ta="right">
        {value}
      </Text>
    </Group>
  );
}

function GaugeRow({ label, value, used, total }: GaugeRowProps) {
  const pct = value ?? (used != null && total != null && total > 0 ? (used / total) * 100 : null);
  const usedStr = formatStorageSize(used);
  const totalStr = formatStorageSize(total);
  const color = pct == null ? "gray" : pct > 90 ? "red" : pct > 75 ? "yellow" : "teal";
  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          {label}
        </Text>
        <Text size="xs" fw={500}>
          {pct != null ? `${pct.toFixed(1)}%` : "—"}
          {used != null && total != null ? ` (${usedStr} / ${totalStr})` : ""}
        </Text>
      </Group>
      <Progress
        value={pct ?? 0}
        color={color}
        size="sm"
        radius="xl"
        aria-label={`${label} usage`}
      />
    </Stack>
  );
}

function formatIo(bytes: number | null): string {
  if (bytes == null) return "—";
  return formatStorageSize(bytes);
}

/**
 * Renders a Mantine Paper card showing CPU, memory, disk and I/O metrics
 * collected by the ctpool worker via psutil.
 */
export function HostCapacityCard({ capacity }: HostCapacityCardProps) {
  const cpuPct = capacity.cpu_percent;
  const cpuColor =
    cpuPct == null ? "gray" : cpuPct > 90 ? "red" : cpuPct > 75 ? "yellow" : "teal";

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Stack gap={2}>
          <Text size="sm" fw={600}>
            Host Capacity
          </Text>
          <Text size="xs" c="dimmed">
            CPU, memory and disk utilisation
          </Text>
        </Stack>

        {/* CPU */}
        <Stack gap={4}>
          <Group justify="space-between">
            <Text size="xs" c="dimmed">
              CPU
            </Text>
            <Text size="xs" fw={500}>
              {cpuPct != null ? `${cpuPct.toFixed(1)}%` : "—"}
            </Text>
          </Group>
          <Progress
            value={cpuPct ?? 0}
            color={cpuColor}
            size="sm"
            radius="xl"
            aria-label="CPU usage"
          />
        </Stack>

        {/* Memory */}
        <GaugeRow
          label="Memory"
          value={capacity.memory_percent}
          used={capacity.memory_used_bytes}
          total={capacity.memory_total_bytes}
        />

        {/* Disk */}
        <GaugeRow
          label="Disk"
          value={capacity.disk_percent}
          used={capacity.disk_used_bytes}
          total={capacity.disk_total_bytes}
        />

        {/* I/O & Network */}
        <SimpleGrid cols={2} spacing="xs">
          <StatRow label="Disk reads" value={formatIo(capacity.disk_io_read_bytes)} />
          <StatRow label="Disk writes" value={formatIo(capacity.disk_io_write_bytes)} />
          <StatRow label="Net sent" value={formatIo(capacity.net_bytes_sent)} />
          <StatRow label="Net recv" value={formatIo(capacity.net_bytes_recv)} />
        </SimpleGrid>
      </Stack>
    </Paper>
  );
}
