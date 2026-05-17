import {
  Button,
  Group,
  Paper,
  RingProgress,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconChartBar, IconEye } from "@tabler/icons-react";
import { ProfileBadge } from "@/components/StatsPanel/ProfileBadge";
import type {
  MaintenanceStatus,
  StorageProfileSettings,
  StorageProjection,
  StorageStats,
} from "@/types";
import { formatStorageSize } from "@/utils/format";
import { computeStorageCeiling } from "@/utils/projectionUtils";

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

interface DiskDonutProps {
  projection: StorageProjection;
}

function DiskDonut({ projection }: DiskDonutProps) {
  const syncPct = projection.sync_percent_by_observation;
  const { ceilingBytes, pct: storagePct } = computeStorageCeiling(projection);

  const hasSyncRing = syncPct != null;
  const hasStorageRing =
    ceilingBytes != null && ceilingBytes > 0 && storagePct != null;

  // Fallback: physical disk ring when no projection data is available at all
  if (!hasSyncRing && !hasStorageRing) {
    const diskUsed = projection.disk_used_bytes;
    const diskTotal = projection.disk_total_bytes;
    if (diskUsed == null || diskTotal == null || diskTotal <= 0) return null;
    const v = Math.min(Math.round((diskUsed / diskTotal) * 100), 100);
    const color = v >= 90 ? "red" : v >= 75 ? "orange" : "teal";
    return (
      <Tooltip
        label={`Disk: ${formatStorageSize(diskUsed)} used of ${formatStorageSize(diskTotal)} total`}
        withArrow
        position="top"
      >
        <Stack gap={0} align="center" style={{ cursor: "default" }}>
          <RingProgress
            size={56}
            thickness={6}
            roundCaps
            sections={[{ value: v, color }]}
            label={
              <Text size="xs" fw={700} ta="center" lh={1}>
                {String(v)}%
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

  const syncV = hasSyncRing ? Math.min(Math.round(syncPct * 100), 100) : 0;
  const syncColor = syncV >= 95 ? "green" : syncV >= 75 ? "teal" : "yellow";
  const completed = projection.planned_observations_completed;
  const total = projection.planned_observations_total;
  const syncTooltip =
    total > 0
      ? `${String(syncV)}% of planned observations ingested (${completed.toLocaleString()} of ${total.toLocaleString()})`
      : `${String(syncV)}% of planned observations ingested`;

  const storageV = hasStorageRing
    ? Math.min(Math.round(storagePct * 100), 100)
    : 0;
  const storageColor =
    projection.projected_fits_on_disk === false ? "orange" : "teal";
  const storageTooltip = `${formatStorageSize(projection.database_size_bytes)} of ~${formatStorageSize(ceilingBytes)} projected max`;

  return (
    <Group gap="xs" wrap="nowrap">
      {hasSyncRing && (
        <Tooltip label={syncTooltip} withArrow position="top">
          <Stack gap={0} align="center" style={{ cursor: "default" }}>
            <RingProgress
              size={56}
              thickness={6}
              roundCaps
              sections={[{ value: syncV, color: syncColor }]}
              label={
                <Text size="xs" fw={700} ta="center" lh={1}>
                  {String(syncV)}%
                </Text>
              }
            />
            <Text size="xs" c="dimmed" ta="center" lh={1}>
              synced
            </Text>
          </Stack>
        </Tooltip>
      )}
      {hasStorageRing && (
        <Tooltip label={storageTooltip} withArrow position="top">
          <Stack gap={0} align="center" style={{ cursor: "default" }}>
            <RingProgress
              size={56}
              thickness={6}
              roundCaps
              sections={[{ value: storageV, color: storageColor }]}
              label={
                <Text size="xs" fw={700} ta="center" lh={1}>
                  {String(storageV)}%
                </Text>
              }
            />
            <Text size="xs" c="dimmed" ta="center" lh={1}>
              used
            </Text>
          </Stack>
        </Tooltip>
      )}
    </Group>
  );
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
          {storageProjection && <DiskDonut projection={storageProjection} />}
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
