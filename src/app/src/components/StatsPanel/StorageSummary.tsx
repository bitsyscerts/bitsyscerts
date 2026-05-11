import { Button, Group, Paper, RingProgress, Stack, Text, Tooltip } from "@mantine/core";
import { IconChartBar, IconEye } from "@tabler/icons-react";
import { ProfileBadge } from "@/components/StatsPanel/ProfileBadge";
import type {
  MaintenanceStatus,
  StorageProfileSettings,
  StorageProjection,
  StorageStats,
} from "@/types";

interface StorageSummaryProps {
  storage: StorageStats;
  storageProfile: StorageProfileSettings | null;
  maintenance: MaintenanceStatus | null | undefined;
  storageProjection?: StorageProjection | null;
  onStorageDetails: () => void;
}

function maintenanceLabel(maintenance: MaintenanceStatus | null | undefined) {
  if (!maintenance) return null;
  switch (maintenance.status) {
    case "never_ran":
      return { text: "Never ran", color: "yellow" };
    case "running":
      return { text: "Running", color: "blue" };
    case "complete":
      return { text: "Complete", color: "green" };
    case "failed":
      return { text: "Failed", color: "red" };
    default:
      return { text: "Unknown", color: "gray" };
  }
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_099_511_627_776) return `${(bytes / 1_099_511_627_776).toFixed(1)} TB`;
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(0)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

interface DiskDonutProps {
  projection: StorageProjection;
}

function DiskDonut({ projection }: DiskDonutProps) {
  // Primary: profile completeness — what % of planned observations are ingested
  const syncPct = projection.sync_percent_by_observation;
  const completed = projection.planned_observations_completed;
  const total = projection.planned_observations_total;

  // Fallback: actual disk usage when no observation plan exists
  const diskUsed = projection.disk_used_bytes;
  const diskTotal = projection.disk_total_bytes;

  if (syncPct != null) {
    const pct = Math.min(Math.round(syncPct * 100), 100);
    const color = pct >= 95 ? "green" : pct >= 75 ? "teal" : "yellow";
    const tooltip =
      total > 0
        ? `${String(pct)}% of planned observations ingested (${completed.toLocaleString()} of ${total.toLocaleString()})`
        : `${String(pct)}% of planned observations ingested`;
    return (
      <Tooltip label={tooltip} withArrow position="top">
        <Stack gap={0} align="center" style={{ cursor: "default" }}>
          <RingProgress
            size={64}
            thickness={7}
            roundCaps
            sections={[{ value: pct, color }]}
            label={
              <Text size="xs" fw={700} ta="center" lh={1}>
                {String(pct)}%
              </Text>
            }
          />
          <Text size="xs" c="dimmed" ta="center" lh={1}>
            synced
          </Text>
        </Stack>
      </Tooltip>
    );
  }

  if (diskUsed != null && diskTotal != null && diskTotal > 0) {
    const pct = Math.min(Math.round((diskUsed / diskTotal) * 100), 100);
    const color = pct >= 90 ? "red" : pct >= 75 ? "orange" : "teal";
    const tooltip = `Disk: ${formatBytes(diskUsed)} used of ${formatBytes(diskTotal)} total`;
    return (
      <Tooltip label={tooltip} withArrow position="top">
        <Stack gap={0} align="center" style={{ cursor: "default" }}>
          <RingProgress
            size={64}
            thickness={7}
            roundCaps
            sections={[{ value: pct, color }]}
            label={
              <Text size="xs" fw={700} ta="center" lh={1}>
                {String(pct)}%
              </Text>
            }
          />
          <Text size="xs" c="dimmed" ta="center" lh={1}>
            disk
          </Text>
        </Stack>
      </Tooltip>
    );
  }

  return null;
}

export function StorageSummary({
  storage,
  storageProfile,
  maintenance,
  storageProjection,
  onStorageDetails,
}: StorageSummaryProps) {
  const maintStatus = maintenanceLabel(maintenance);

  return (
    <Paper withBorder radius="md" p="sm">
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs">
            <IconChartBar size={16} />
            <Text size="sm" fw={700}>
              Storage
            </Text>
          </Group>
          <Button
            variant="subtle"
            size="xs"
            leftSection={<IconEye size={14} />}
            onClick={onStorageDetails}
          >
            Storage details
          </Button>
        </Group>

        <Group gap="md" wrap="nowrap" align="flex-start">
          {storageProjection && (
            <DiskDonut projection={storageProjection} />
          )}
          <Group gap="md" wrap="wrap" style={{ flex: 1 }}>
            {storageProfile && (
              <Stack gap={2}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                  Profile
                </Text>
                <ProfileBadge profile={storageProfile.storage_profile} />
              </Stack>
            )}
            <Stack gap={2}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                Used
              </Text>
              <Text size="md" fw={700}>
                {storage.total_size_pretty}
              </Text>
            </Stack>
            {maintStatus && (
              <Stack gap={2}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                  Maintenance
                </Text>
                <Text size="sm" fw={600} c={maintStatus.color}>
                  {maintStatus.text}
                </Text>
              </Stack>
            )}
          </Group>
        </Group>
      </Stack>
    </Paper>
  );
}
