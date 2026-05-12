import { Drawer, ScrollArea } from "@mantine/core";
import { IconUsers } from "@tabler/icons-react";
import { DrawerFooter } from "@/components/DetailDrawer/DrawerFooter";
import { DrawerHeader } from "@/components/DetailDrawer/DrawerHeader";
import { WorkerActivityCard } from "@/components/StatsPanel/WorkerActivityCard";
import type { WorkerSummary } from "@/types";

interface WorkerDetailsDrawerProps {
  opened: boolean;
  onClose: () => void;
  workers: WorkerSummary | null;
}

export function WorkerDetailsDrawer({
  opened,
  onClose,
  workers,
}: WorkerDetailsDrawerProps) {
  return (
    <Drawer
      opened={opened}
      onClose={onClose}
      position="right"
      size="lg"
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
        icon={<IconUsers size={20} />}
        title="Worker Activity"
        description="Active ingestion workers and their current heartbeat status."
      />
      <ScrollArea style={{ flex: 1 }} p="md">
        {workers && <WorkerActivityCard workers={workers} />}
      </ScrollArea>
      <DrawerFooter onBack={onClose} />
    </Drawer>
  );
}
