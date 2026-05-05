import { Switch } from "@mantine/core";

interface IncludeCertsToggleProps {
  value: boolean;
  onChange: (value: boolean) => void;
}

/**
 * Switch that enables embedding the latest certificate data in each hostname
 * search result row.
 */
export function IncludeCertsToggle({
  value,
  onChange,
}: IncludeCertsToggleProps) {
  return (
    <Switch
      checked={value}
      onChange={(e) => onChange(e.currentTarget.checked)}
      label="Include certs"
      description="Embed latest cert in results"
      size="sm"
    />
  );
}
