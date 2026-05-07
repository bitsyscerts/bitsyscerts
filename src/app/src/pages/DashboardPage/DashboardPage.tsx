import { Suspense } from "react";
import {
  ActionIcon,
  Alert,
  Container,
  Grid,
  Group,
  Stack,
  Text,
} from "@mantine/core";
import { IconAlertTriangle, IconRefresh } from "@tabler/icons-react";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { AuditHealthCard } from "@/components/StatsPanel/AuditHealthCard";
import { BackfillRangesCard } from "@/components/StatsPanel/BackfillRangesCard";
import { DbContentionCard } from "@/components/StatsPanel/DbContentionCard";
import { IngestionRateCard } from "@/components/StatsPanel/IngestionRateCard";
import { LogStatsFilter } from "@/components/StatsPanel/LogStatsFilter";
import { LogStatsList } from "@/components/StatsPanel/LogStatsList";
import { StatsPanelSkeleton } from "@/components/StatsPanel/StatsPanelSkeleton";
import { StatsSummary } from "@/components/StatsPanel/StatsSummary";
import { StorageProfileCard } from "@/components/StatsPanel/StorageProfileCard";
import { StorageProjectionCard } from "@/components/StatsPanel/StorageProjectionCard";
import { StorageTable } from "@/components/StatsPanel/StorageTable";
import { TailFreshnessCard } from "@/components/StatsPanel/TailFreshnessCard";
import { useLogFilter } from "@/hooks/useLogFilter";
import { useStats } from "@/hooks/useStats";
import type { LogStatsItem, StatsResponse } from "@/types";

const AUTO_REFRESH_MS = 10_000;

interface LogsSectionProps {
  logs: LogStatsItem[];
}

function LogsSection({ logs }: LogsSectionProps) {
  const {
    query,
    setQuery,
    stateFilter,
    setStateFilter,
    hideSynced,
    setHideSynced,
    filtered,
  } = useLogFilter(logs);

  return (
    <Stack gap="sm">
      <Text size="sm" fw={600}>
        CT Logs
      </Text>
      <LogStatsFilter
        query={query}
        stateFilter={stateFilter}
        hideSynced={hideSynced}
        onQueryChange={setQuery}
        onStateFilterChange={setStateFilter}
        onHideSyncedChange={setHideSynced}
        totalCount={logs.length}
        filteredCount={filtered.length}
      />
      <LogStatsList logs={filtered} />
    </Stack>
  );
}

interface RefreshBarProps {
  updatedAt: number;
  onRefresh: () => void;
}

function RefreshBar({ updatedAt, onRefresh }: RefreshBarProps) {
  const ts = updatedAt > 0 ? new Date(updatedAt).toLocaleTimeString() : null;
  return (
    <Group justify="flex-end" align="center" gap="xs">
      {ts && (
        <Text size="xs" c="dimmed">
          Updated {ts}
        </Text>
      )}
      <ActionIcon
        onClick={onRefresh}
        variant="subtle"
        size="sm"
        aria-label="Refresh statistics"
      >
        <IconRefresh size={14} />
      </ActionIcon>
    </Group>
  );
}

interface LeftColProps {
  data: StatsResponse;
}

function DashboardLeftCol({ data }: LeftColProps) {
  return (
    <Stack>
      <StatsSummary
        totalHostnames={data.total_hostnames}
        totalCertificates={data.total_certificates}
        totalLogs={data.total_logs}
      />
      <IngestionRateCard ingestionRate={data.ingestion_rate} />
      <TailFreshnessCard tailFreshness={data.tail_freshness} />
      <BackfillRangesCard backfillRanges={data.backfill_ranges} />
      {data.audit_health && <AuditHealthCard auditHealth={data.audit_health} />}
      <StorageProjectionCard projection={data.storage_projection} />
      <DbContentionCard contention={data.db_contention} />
    </Stack>
  );
}

interface RightColProps {
  data: StatsResponse;
}

function DashboardRightCol({ data }: RightColProps) {
  return (
    <Stack gap="lg">
      {data.storage_profile && (
        <StorageProfileCard storageProfile={data.storage_profile} />
      )}
      <Stack gap="sm">
        <Text size="sm" fw={600}>
          Database Storage
        </Text>
        <StorageTable
          tables={data.storage.tables}
          totalSizeBytes={data.storage.total_size_bytes}
        />
      </Stack>
      <LogsSection logs={data.logs} />
    </Stack>
  );
}

/**
 * Dashboard content: fetches stats with 10 s auto-refresh (paused when tab
 * is hidden), shows all operational panels, and provides a manual refresh
 * button with a last-updated timestamp.
 */
function DashboardContent() {
  const { data, isLoading, isError, dataUpdatedAt, refetch } =
    useStats(AUTO_REFRESH_MS);

  if (isLoading) return <StatsPanelSkeleton />;

  if (isError || !data) {
    return (
      <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light">
        Could not load statistics.
      </Alert>
    );
  }

  return (
    <Stack gap="md">
      <RefreshBar
        updatedAt={dataUpdatedAt}
        onRefresh={() => {
          void refetch();
        }}
      />
      <Grid gutter="lg" align="flex-start">
        <Grid.Col span={{ base: 12, md: 4, lg: 3 }}>
          <DashboardLeftCol data={data} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 8, lg: 9 }}>
          <DashboardRightCol data={data} />
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

/** Dashboard home page: all operational stats with automatic 10 s refresh. */
export function DashboardPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<StatsPanelSkeleton />}>
        <Container size="xl" py="md">
          <DashboardContent />
        </Container>
      </Suspense>
    </ErrorBoundary>
  );
}
