import { Switch } from "@mantine/core";

interface RecursiveToggleProps {
  value: boolean;
  onChange: (value: boolean) => void;
}

/**
 * Switch for the recursive search option — searches by registrable domain
 * instead of exact hostname match when enabled.
 */
export function RecursiveToggle({ value, onChange }: RecursiveToggleProps) {
  return (
    <Switch
      checked={value}
      onChange={(e) => onChange(e.currentTarget.checked)}
      label="Recursive"
      description="Search by registrable domain"
      size="sm"
    />
  );
}
