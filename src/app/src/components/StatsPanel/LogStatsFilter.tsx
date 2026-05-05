import { useState } from "react";
import {
  Box,
  Chip,
  Collapse,
  Group,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import {
  IconChevronDown,
  IconChevronUp,
  IconSearch,
} from "@tabler/icons-react";

const STATE_OPTIONS = [
  { value: "usable", label: "Usable", color: "green" },
  { value: "readonly", label: "Readonly", color: "blue" },
  { value: "retired", label: "Retired", color: "red" },
  { value: "pending", label: "Pending", color: "yellow" },
] as const;

interface LogStatsFilterProps {
  query: string;
  stateFilter: string[];
  onQueryChange: (q: string) => void;
  onStateFilterChange: (states: string[]) => void;
  totalCount: number;
  filteredCount: number;
}

/**
 * Search bar and collapsible state-chip filter for the CT log list.
 * Text matches any searchable field; chips filter by log_state.
 */
export function LogStatsFilter({
  query,
  stateFilter,
  onQueryChange,
  onStateFilterChange,
  totalCount,
  filteredCount,
}: LogStatsFilterProps) {
  const [open, setOpen] = useState(false);

  const countLabel =
    filteredCount < totalCount
      ? `${String(filteredCount)} / ${String(totalCount)}`
      : String(totalCount);

  return (
    <Box>
      <Group gap="xs" mb={open ? "xs" : 0} wrap="nowrap">
        <TextInput
          placeholder="Filter logs…"
          leftSection={<IconSearch size={14} />}
          value={query}
          onChange={(e) => {
            onQueryChange(e.currentTarget.value);
          }}
          size="xs"
          style={{ flex: 1 }}
        />
        <UnstyledButton
          onClick={() => {
            setOpen((o) => !o);
          }}
          style={{ display: "flex", alignItems: "center", gap: 4 }}
        >
          <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
            States
          </Text>
          {open ? (
            <IconChevronUp size={12} color="var(--mantine-color-dimmed)" />
          ) : (
            <IconChevronDown size={12} color="var(--mantine-color-dimmed)" />
          )}
        </UnstyledButton>
        <Text size="xs" c="dimmed" style={{ whiteSpace: "nowrap" }}>
          {countLabel}
        </Text>
      </Group>
      <Collapse in={open}>
        <Chip.Group multiple value={stateFilter} onChange={onStateFilterChange}>
          <Group gap="xs" mb="xs">
            {STATE_OPTIONS.map(({ value, label, color }) => (
              <Chip key={value} value={value} size="xs" color={color}>
                {label}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
      </Collapse>
    </Box>
  );
}
