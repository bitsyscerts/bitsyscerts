import { Box, Drawer, ScrollArea, Stack } from "@mantine/core";
import { IconChartBar } from "@tabler/icons-react";
import { DrawerFooter } from "@/components/DetailDrawer/DrawerFooter";
import { DrawerHeader } from "@/components/DetailDrawer/DrawerHeader";
import { MaintenancePanel } from "@/components/StatsPanel/MaintenancePanel";
import { StorageProjectionCard } from "@/components/StatsPanel/StorageProjectionCard";
import { StorageTable } from "@/components/StatsPanel/StorageTable";
import type {
  MaintenanceStatus,
  StorageProjection,
  StorageStats,
} from "@/types";

interface StorageDetailsDrawerProps {
  opened: boolean;
  onClose: () => void;
  storage: StorageStats;
  projection: StorageProjection;
  maintenance: MaintenanceStatus | null | undefined;
}

export function StorageDetailsDrawer({
  opened,
  onClose,
  storage,
  projection,
  maintenance,
}: StorageDetailsDrawerProps) {
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
        icon={<IconChartBar size={20} />}
        title="Storage Details"
        description="Database storage breakdown, projected growth, and maintenance status."
      />
      <ScrollArea style={{ flex: 1 }}>
        <Box p="md">
          <Stack gap="md">
            <StorageProjectionCard projection={projection} />
            <StorageTable
              tables={storage.tables}
              totalSizeBytes={storage.total_size_bytes}
            />
            {maintenance && <MaintenancePanel maintenance={maintenance} />}
          </Stack>
        </Box>
      </ScrollArea>
      <DrawerFooter onBack={onClose} />
    </Drawer>
  );
}
