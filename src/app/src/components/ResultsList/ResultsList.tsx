import { Group, Stack, Text } from "@mantine/core";
import type { CertEmbedResponse, HostnameResult } from "@/types";
import { HostnameResultRow } from "@/components/ResultRow/HostnameResultRow";
import { ResultRowSkeleton } from "@/components/ResultRow/ResultRowSkeleton";
import { PaginationControls } from "./PaginationControls";
import { ExportButton } from "./ExportButton";

interface ResultsListProps {
  items: HostnameResult[];
  isLoading: boolean;
  onRowClick: (item: HostnameResult) => void;
  onCertClick?: (cert: CertEmbedResponse) => void;
  currentPage: number;
  knownPageCount: number;
  estimatedPageCount: number | null;
  totalEstimate: number | null;
  isOverLimit: boolean;
  onGoToPage: (page: number) => void;
}

const SKELETON_COUNT = 5;

/**
 * Renders HostnameResult rows, skeleton placeholders while loading, an
 * empty-state message, and pagination + export controls.
 */
export function ResultsList({
  items,
  isLoading,
  onRowClick,
  onCertClick,
  currentPage,
  knownPageCount,
  estimatedPageCount,
  totalEstimate,
  isOverLimit,
  onGoToPage,
}: ResultsListProps) {
  if (isLoading) {
    return (
      <Stack gap="sm">
        {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
          // biome-ignore lint: index key acceptable for static skeleton list
          <ResultRowSkeleton key={i} />
        ))}
      </Stack>
    );
  }

  if (items.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No results found. Try a different query or adjust the search options.
      </Text>
    );
  }

  return (
    <Stack gap="sm">
      <Group justify="flex-end">
        <ExportButton items={items} />
      </Group>

      {items.map((item) => (
        <HostnameResultRow
          key={item.id}
          item={item}
          onClick={onRowClick}
          onCertClick={onCertClick}
        />
      ))}

      <PaginationControls
        currentPage={currentPage}
        knownPageCount={knownPageCount}
        estimatedPageCount={estimatedPageCount}
        totalEstimate={totalEstimate}
        isOverLimit={isOverLimit}
        onGoToPage={onGoToPage}
      />
    </Stack>
  );
}
