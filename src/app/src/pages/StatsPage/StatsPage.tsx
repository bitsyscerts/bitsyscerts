import { Suspense, useState } from "react";
import {
  Alert,
  Checkbox,
  Container,
  Grid,
  Group,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { StatsSummary } from "@/components/StatsPanel/StatsSummary";
import { StorageTable } from "@/components/StatsPanel/StorageTable";
import { LogStatsList } from "@/components/StatsPanel/LogStatsList";
import { LogStatsFilter } from "@/components/StatsPanel/LogStatsFilter";
import { StatsPanelSkeleton } from "@/components/StatsPanel/StatsPanelSkeleton";
import { useStats } from "@/hooks/useStats";
import { useLogFilter } from "@/hooks/useLogFilter";
import type { LogStatsItem } from "@/types";

const WATCH_INTERVAL = 1_000;
const DEFAULT_INTERVAL = 60_000;

interface LogsSectionProps {
  logs: LogStatsItem[];
}

/** CT Logs section with client-side text + state filtering. */
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

/**
 * Full-page statistics view. On desktop, stat counters fill the left 1/3 and
 * the storage breakdown occupies the right 2/3. CT Logs appear below with a
 * persistent client-side filter.
 */
function StatsContent() {
  const [watching, setWatching] = useState(true);
  const { data, isLoading, isError } = useStats(
    watching ? WATCH_INTERVAL : DEFAULT_INTERVAL,
  );

  if (isLoading) return <StatsPanelSkeleton />;

  if (isError || !data) {
    return (
      <Alert icon={<IconAlertTriangle size={16} />} color="red" variant="light">
        Could not load statistics.
      </Alert>
    );
  }

  return (
    <Stack gap="lg">
      <Grid gutter="lg" align="stretch">
        <Grid.Col span={{ base: 12, sm: 3 }}>
          <Stack justify="center" h="100%">
            <StatsSummary
              totalHostnames={data.total_hostnames}
              totalCertificates={data.total_certificates}
              totalLogs={data.total_logs}
            />
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 9 }}>
          <Stack gap="sm">
            <Group justify="space-between" align="center">
              <Text size="sm" fw={600}>
                Database Storage
              </Text>
              <Tooltip label="Refresh every 1 s" position="left" withArrow>
                <Checkbox
                  label="Watch"
                  size="xs"
                  checked={watching}
                  onChange={(e) => {
                    setWatching(e.currentTarget.checked);
                  }}
                />
              </Tooltip>
            </Group>
            <StorageTable
              tables={data.storage.tables}
              totalSizeBytes={data.storage.total_size_bytes}
            />
          </Stack>
        </Grid.Col>
      </Grid>
      <LogsSection logs={data.logs} />
    </Stack>
  );
}

/**
 * Stats page: wraps StatsContent in ErrorBoundary + Suspense with skeleton.
 */
export function StatsPage() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<StatsPanelSkeleton />}>
        <Container size="xl" py="md">
          <StatsContent />
        </Container>
      </Suspense>
    </ErrorBoundary>
  );
}
