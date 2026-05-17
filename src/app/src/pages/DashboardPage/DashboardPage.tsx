import { Suspense } from "react";
import { Container } from "@mantine/core";
import { AnnouncementBanner } from "@/components/AppShell/AnnouncementBanner";
import { ErrorBoundary } from "@/components/ErrorBoundary/ErrorBoundary";
import { StatsPanelSkeleton } from "@/components/StatsPanel/StatsPanelSkeleton";
import { DashboardOverview } from "./DashboardOverview";

/** Dashboard home page: all operational stats with automatic 10 s refresh. */
export function DashboardPage() {
  return (
    <ErrorBoundary>
      <Container size="xl" px="md">
        <AnnouncementBanner />
      </Container>
      <Suspense fallback={<StatsPanelSkeleton />}>
        <Container size="xl" py="md">
          <DashboardOverview />
        </Container>
      </Suspense>
    </ErrorBoundary>
  );
}
