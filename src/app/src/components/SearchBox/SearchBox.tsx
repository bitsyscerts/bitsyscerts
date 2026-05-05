import { type KeyboardEvent } from "react";
import { TextInput, ActionIcon } from "@mantine/core";
import { IconSearch, IconX } from "@tabler/icons-react";

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

/**
 * Controlled search input that fires onSearch on Enter keypress or the search
 * button click. Includes a clear (×) button when the field has a value.
 */
export function SearchBox({
  value,
  onChange,
  onSearch,
  placeholder = "Search hostnames…",
  disabled = false,
}: SearchBoxProps) {
  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") onSearch(value);
  }

  function handleClear() {
    onChange("");
    onSearch("");
  }

  const rightSection = value ? (
    <ActionIcon
      variant="subtle"
      size="sm"
      onClick={handleClear}
      aria-label="Clear search"
    >
      <IconX size={14} />
    </ActionIcon>
  ) : null;

  return (
    <TextInput
      value={value}
      onChange={(e) => {
        onChange(e.currentTarget.value);
      }}
      onKeyDown={handleKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      size="md"
      radius="md"
      style={{ flex: 1 }}
      leftSection={<IconSearch size={16} />}
      rightSection={rightSection}
      rightSectionPointerEvents="all"
      aria-label="Search query"
    />
  );
}
