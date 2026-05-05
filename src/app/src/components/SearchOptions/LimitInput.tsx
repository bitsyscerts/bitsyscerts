import { NumberInput } from "@mantine/core";

interface LimitInputProps {
  value: number;
  onChange: (value: number) => void;
}

/**
 * Number input for the results page limit (1–200).
 */
export function LimitInput({ value, onChange }: LimitInputProps) {
  return (
    <NumberInput
      label="Limit"
      description="Results per page"
      value={value}
      onChange={(v) => onChange(Number(v))}
      min={1}
      max={200}
      size="sm"
      aria-label="Results limit"
    />
  );
}
