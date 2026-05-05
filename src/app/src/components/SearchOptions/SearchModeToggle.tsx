import { SegmentedControl } from "@mantine/core";
import type { SearchMode } from "@/types";

interface SearchModeToggleProps {
  value: SearchMode;
  onChange: (value: SearchMode) => void;
}

const DATA = [
  { label: "Hostnames", value: "hostnames" },
  { label: "Certificates", value: "certificates" },
];

/**
 * Segmented control that switches between hostnames search and certificate
 * fingerprint lookup modes.
 */
export function SearchModeToggle({ value, onChange }: SearchModeToggleProps) {
  return (
    <SegmentedControl
      value={value}
      onChange={(v) => {
        onChange(v as SearchMode);
      }}
      data={DATA}
      size="sm"
      radius="md"
    />
  );
}
