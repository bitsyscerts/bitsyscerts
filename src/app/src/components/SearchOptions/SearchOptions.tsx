import { SimpleGrid, Stack } from "@mantine/core";
import { RecursiveToggle } from "./RecursiveToggle";
import { DepthInput } from "./DepthInput";
import { SortSelect } from "./SortSelect";
import { LimitInput } from "./LimitInput";
import { IncludeCertsToggle } from "./IncludeCertsToggle";
import type { SortField } from "@/types";

interface SearchOptionsProps {
  recursive: boolean;
  onRecursiveChange: (v: boolean) => void;
  depth: number | null;
  onDepthChange: (v: number | null) => void;
  sort: SortField;
  onSortChange: (v: SortField) => void;
  limit: number;
  onLimitChange: (v: number) => void;
  includeCerts: boolean;
  onIncludeCertsChange: (v: boolean) => void;
}

/**
 * Hostname search option controls in a responsive grid. Rendered only when the
 * parent explicitly shows the options panel (controlled by a filter toggle).
 *
 * Layout (≥ md): [Recursive + Depth] [Sort] [Limit] [Include Certs]
 * Depth nests below Recursive in the same cell so it never creates a
 * gap when hidden.
 */
export function SearchOptions({
  recursive,
  onRecursiveChange,
  depth,
  onDepthChange,
  sort,
  onSortChange,
  limit,
  onLimitChange,
  includeCerts,
  onIncludeCertsChange,
}: SearchOptionsProps) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="md">
      <Stack gap="xs" justify="flex-start">
        <RecursiveToggle value={recursive} onChange={onRecursiveChange} />
        {recursive && (
          <DepthInput value={depth} onChange={onDepthChange} />
        )}
      </Stack>
      <SortSelect value={sort} onChange={onSortChange} />
      <LimitInput value={limit} onChange={onLimitChange} />
      <IncludeCertsToggle
        value={includeCerts}
        onChange={onIncludeCertsChange}
      />
    </SimpleGrid>
  );
}
