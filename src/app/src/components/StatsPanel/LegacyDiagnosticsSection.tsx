import { Accordion, Stack, Text } from "@mantine/core";

import type { AuditHealth, BackfillRangeStats } from "@/types/stats";

import { AuditHealthCard } from "./AuditHealthCard";
import { BackfillRangesCard } from "./BackfillRangesCard";

interface LegacyDiagnosticsSectionProps {
  backfillRanges: BackfillRangeStats;
  auditHealth?: AuditHealth | null;
  title?: string;
}

export function LegacyDiagnosticsSection({
  backfillRanges,
  auditHealth = null,
  title = "Advanced / Legacy Range State",
}: LegacyDiagnosticsSectionProps) {
  return (
    <Accordion variant="separated" radius="md">
      <Accordion.Item value="legacy-ranges">
        <Accordion.Control>
          <Text size="sm" fw={500} c="dimmed">
            {title}
          </Text>
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap="xs">
            <Text size="xs" c="dimmed">
              Legacy range state is retained for compatibility with older
              ingestion runs and legacy dispatch mode. Current per-log dispatch
              uses <code>ct_log_backfill_state</code> as the primary source of
              backfill progress.
            </Text>
            <BackfillRangesCard
              backfillRanges={backfillRanges}
              isPrimary={false}
            />
            {auditHealth && (
              <AuditHealthCard auditHealth={auditHealth} isPrimary={false} />
            )}
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
