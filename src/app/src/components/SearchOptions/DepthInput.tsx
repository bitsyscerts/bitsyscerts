import { NumberInput } from "@mantine/core";

interface DepthInputProps {
  value: number | null;
  onChange: (value: number | null) => void;
  visible: boolean;
}

/**
 * Number input for the sub-label depth limit; only rendered when recursive=true.
 */
export function DepthInput({ value, onChange, visible }: DepthInputProps) {
  if (!visible) return null;

  return (
    <NumberInput
      label="Depth"
      description="Sub-label depth limit"
      value={value ?? ""}
      onChange={(v) => {
        onChange(v === "" ? null : Number(v));
      }}
      min={0}
      size="sm"
      placeholder="No limit"
      aria-label="Depth limit"
    />
  );
}
