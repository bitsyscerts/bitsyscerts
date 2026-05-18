/*
 * NOTE (201–500 line warning): This file exceeds the 200-line preference.
 * Consolidation is justified because StorageProjectionCard is a single
 * cohesive presentation unit with available/unavailable branching and a
 * collapsible details section. Splitting DetailItem helpers into a shared
 * atoms file would resolve this; defer until a second card reuses them.
 */
import { useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Collapse,
  Group,
  Paper,
  RingProgress,
  SimpleGrid,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { BackfillWorkloadSection } from "@/components/StatsPanel/BackfillWorkloadSection";
import { ProfileBadge } from "@/components/StatsPanel/ProfileBadge";
import { ProjectionConfidenceBadge } from "@/components/StatsPanel/ProjectionConfidenceBadge";
import { RetainedStorageSection } from "@/components/StatsPanel/RetainedStorageSection";
import type { StorageProjection } from "@/types";
import {
  formatCompactNumber,
  formatObservationDensity,
  formatRatioPct,
  formatStorageSize,
} from "@/utils/format";
import { computeStorageCeiling } from "@/utils/projectionUtils";

interface StorageProjectionCardProps {
  projection: StorageProjection;
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

function warningMessage(projection: StorageProjection): string | null {
  if (projection.status !== "available") return null;
  if (projection.projected_fits_on_disk !== false) return null;
  return (
    projection.notes.find((note) => note.includes("disk")) ??
    "Projected size may exceed available disk space."
  );
}

function unavailableMessage(projection: StorageProjection): string {
  return (
    projection.notes[0] ??
    "Storage projection unavailable. Backfill ranges or observation counts are not available yet."
  );
}

export function StorageProjectionCard({
  projection,
}: StorageProjectionCardProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const warning = warningMessage(projection);
  const { pct } = computeStorageCeiling(projection);
  const storageValue = (pct ?? 0) * 100;
  const syncPct = projection.sync_percent_by_observation;

  return (
    <Paper withBorder radius="md" p="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Storage Projection
            </Text>
            <Text size="xs" c="dimmed">
              Storage used vs projected
            </Text>
          </Stack>
          <Group gap="xs">
            <ProfileBadge profile={projection.profile} />
            <ProjectionConfidenceBadge confidence={projection.confidence} />
            <Badge
              variant="light"
              color={
                (projection.sync_percent_by_observation ?? 0) >= 1
                  ? "teal"
                  : "gray"
              }
            >
              {(projection.sync_percent_by_observation ?? 0) >= 1
                ? "Actual"
                : "Estimate"}
            </Badge>
          </Group>
        </Group>

        {projection.status === "available" ? (
          <Stack gap="md">
            <Group align="center" gap="md" wrap="wrap">
              <RingProgress
                size={132}
                thickness={14}
                roundCaps
                rootColor="gray.3"
                sections={[
                  {
                    value: Math.min(storageValue, 100),
                    color: warning ? "orange" : "teal",
                  },
                ]}
                label={
                  <Stack gap={0} align="center">
                    <Text fw={700} size="lg">
                      {formatRatioPct(storageValue / 100)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      used
                    </Text>
                  </Stack>
                }
              />
              {syncPct != null && (
                <RingProgress
                  size={132}
                  thickness={14}
                  roundCaps
                  rootColor="gray.3"
                  sections={[
                    {
                      value: Math.min(Math.round(syncPct * 100), 100),
                      color:
                        syncPct >= 0.95
                          ? "green"
                          : syncPct >= 0.75
                            ? "teal"
                            : "yellow",
                    },
                  ]}
                  label={
                    <Stack gap={0} align="center">
                      <Text fw={700} size="lg">
                        {formatRatioPct(syncPct)}
                      </Text>
                      <Text size="xs" c="dimmed">
                        synced
                      </Text>
                    </Stack>
                  }
                />
              )}
              <Stack gap={4} maw={280}>
                <RetainedStorageSection projection={projection} />
                {projection.ingestion_workload != null ? (
                  <BackfillWorkloadSection
                    workload={projection.ingestion_workload}
                  />
                ) : (
                  <>
                    <Text size="sm" fw={600}>
                      Sync estimate
                    </Text>
                    <Text size="sm" c="dimmed">
                      {formatCompactNumber(
                        projection.planned_observations_completed,
                      )}{" "}
                      /{" "}
                      {formatCompactNumber(
                        projection.planned_observations_total,
                      )}{" "}
                      observations
                    </Text>
                  </>
                )}
              </Stack>
            </Group>

            <Button
              variant="subtle"
              color="gray"
              size="compact-sm"
              px={0}
              justify="flex-start"
              onClick={() => {
                setDetailsOpen((open) => !open);
              }}
            >
              {detailsOpen ? "Hide details" : "Show details"}
            </Button>

            <Collapse expanded={detailsOpen}>
              <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
                <DetailItem
                  label="Projected range"
                  value={`${formatStorageSize(projection.projection_low_bytes)} - ${formatStorageSize(projection.projection_high_bytes)}`}
                />
                <DetailItem
                  label="Current density"
                  value={formatObservationDensity(
                    projection.bytes_per_observation_current,
                  )}
                />
                <DetailItem
                  label="Disk free now"
                  value={formatStorageSize(projection.disk_free_bytes)}
                />
                <DetailItem
                  label="Projected free after"
                  value={formatStorageSize(
                    projection.projected_disk_free_after_sync_bytes,
                  )}
                />
              </SimpleGrid>
            </Collapse>
          </Stack>
        ) : (
          <Alert color="gray" variant="light">
            {unavailableMessage(projection)}
          </Alert>
        )}

        {warning ? (
          <Alert
            icon={<IconAlertTriangle size={16} />}
            color="orange"
            variant="light"
          >
            {warning}
          </Alert>
        ) : null}
      </Stack>
    </Paper>
  );
}
