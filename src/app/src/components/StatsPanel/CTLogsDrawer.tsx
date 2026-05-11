import { Box, Drawer, ScrollArea, Stack } from "@mantine/core";
import { IconDatabase } from "@tabler/icons-react";
import { DrawerFooter } from "@/components/DetailDrawer/DrawerFooter";
import { DrawerHeader } from "@/components/DetailDrawer/DrawerHeader";
import { BackfillStateCard } from "@/components/StatsPanel/BackfillStateCard";
import { LogStatsFilter } from "@/components/StatsPanel/LogStatsFilter";
import { LogStatsList } from "@/components/StatsPanel/LogStatsList";
import { useLogFilter } from "@/hooks/useLogFilter";
import type { BackfillStateSummary, LogStatsItem } from "@/types";

interface CTLogsDrawerProps {
  opened: boolean;
  onClose: () => void;
  logs: LogStatsItem[];
  backfillState: BackfillStateSummary | null;
}

export function CTLogsDrawer({
  opened,
  onClose,
  logs,
  backfillState,
}: CTLogsDrawerProps) {
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
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="xl"
      withCloseButton={false}
      styles={{
        body: {
          padding: 0,
          display: "flex",
          flexDirection: "column",
          height: "100%",
        },
      }}
    >
      <DrawerHeader
        icon={<IconDatabase size={20} />}
        title="CT Logs"
        description="Certificate Transparency log sources, backfill progress, and tail status."
      />
      <ScrollArea style={{ flex: 1 }}>
        <Box p="md">
          <Stack gap="md">
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
            {backfillState && <BackfillStateCard state={backfillState} />}
          </Stack>
        </Box>
      </ScrollArea>
      <DrawerFooter onBack={onClose} />
    </Drawer>
  );
}
