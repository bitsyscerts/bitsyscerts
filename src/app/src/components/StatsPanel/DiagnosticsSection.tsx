import { Accordion, Stack } from "@mantine/core";
import { AuditHealthCard } from "@/components/StatsPanel/AuditHealthCard";
import { BackfillRangesCard } from "@/components/StatsPanel/BackfillRangesCard";
import { DbContentionCard } from "@/components/StatsPanel/DbContentionCard";
import type {
  AuditHealth,
  BackfillRangeStats,
  DbContentionStats,
} from "@/types";

interface DiagnosticsSectionProps {
  backfillRanges: BackfillRangeStats;
  auditHealth: AuditHealth | null;
  contention: DbContentionStats;
}

export function DiagnosticsSection({
  backfillRanges,
  auditHealth,
  contention,
}: DiagnosticsSectionProps) {
  return (
    <Accordion variant="separated" radius="md">
      <Accordion.Item value="diagnostics">
        <Accordion.Control>Advanced diagnostics</Accordion.Control>
        <Accordion.Panel>
          <Stack gap="md">
            <BackfillRangesCard backfillRanges={backfillRanges} />
            {auditHealth && <AuditHealthCard auditHealth={auditHealth} />}
            <DbContentionCard contention={contention} />
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
