import { NumberInput } from "@mantine/core";

interface DepthInputProps {
  value: number | null;
  onChange: (value: number | null) => void;
}

/**
 * Number input for the sub-label depth limit.
 * Visibility is controlled by the parent — only rendered when recursive=true.
 */
export function DepthInput({ value, onChange }: DepthInputProps) {
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
