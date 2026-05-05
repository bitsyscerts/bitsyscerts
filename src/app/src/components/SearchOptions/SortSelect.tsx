import { Select } from "@mantine/core";
import { SORT_FIELD_LABELS, type SortField } from "@/types";

interface SortSelectProps {
  value: SortField;
  onChange: (value: SortField) => void;
}

const DATA = (Object.entries(SORT_FIELD_LABELS) as [SortField, string][]).map(
  ([value, label]) => ({ value, label }),
);

/**
 * Select input populated with all four SortField enum values from the API.
 */
export function SortSelect({ value, onChange }: SortSelectProps) {
  return (
    <Select
      label="Sort"
      data={DATA}
      value={value}
      onChange={(v) => {
        onChange(v as SortField);
      }}
      size="sm"
      allowDeselect={false}
      aria-label="Sort order"
    />
  );
}
