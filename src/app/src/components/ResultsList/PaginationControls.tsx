import { Group, Pagination, Text } from "@mantine/core";

interface PaginationControlsProps {
  currentPage: number;
  /** Number of pages with cached cursors — pages beyond this are disabled. */
  knownPageCount: number;
  /**
   * Upfront estimated total pages (from total_estimate / limit).
   * Null until the first response arrives. Falls back to knownPageCount.
   */
  estimatedPageCount: number | null;
  totalEstimate: number | null;
  isOverLimit: boolean;
  onGoToPage: (page: number) => void;
}

function formatCount(
  totalEstimate: number | null,
  isOverLimit: boolean,
): string | null {
  if (totalEstimate == null) return null;
  if (isOverLimit) return "More than 10,000 matches";
  return `${totalEstimate.toLocaleString()} match${totalEstimate !== 1 ? "es" : ""}`;
}

/**
 * Prev/next page navigation with numbered page buttons and a total-count label.
 *
 * All estimated pages are shown upfront so the user has "object permanence".
 * Pages beyond the cursor cache are rendered but disabled; they enable
 * automatically as the user navigates forward and cursors are cached.
 */
export function PaginationControls({
  currentPage,
  knownPageCount,
  estimatedPageCount,
  totalEstimate,
  isOverLimit,
  onGoToPage,
}: PaginationControlsProps) {
  const total = estimatedPageCount ?? knownPageCount;
  const countText = formatCount(totalEstimate, isOverLimit);

  return (
    <Group justify="space-between" align="center" mt="xs" wrap="wrap" gap="xs">
      <Text size="xs" c="dimmed">
        {countText ?? ""}
      </Text>
      {total > 1 && (
        <Pagination.Root
          total={total}
          value={currentPage}
          onChange={onGoToPage}
          size="sm"
          siblings={1}
          boundaries={1}
          getItemProps={(page) => ({
            disabled: page > knownPageCount,
          })}
        >
          <Group gap={7} wrap="nowrap">
            <Pagination.Previous disabled={currentPage <= 1} />
            <Pagination.Items />
            <Pagination.Next disabled={currentPage >= knownPageCount} />
          </Group>
        </Pagination.Root>
      )}
    </Group>
  );
}
