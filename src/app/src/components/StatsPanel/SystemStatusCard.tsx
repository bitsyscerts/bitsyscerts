import { Group, Paper, Text, ThemeIcon } from "@mantine/core";
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleX,
  IconLoader,
  IconQuestionMark,
} from "@tabler/icons-react";
import type { SystemStatusLevel } from "@/utils/deriveSystemStatus";

interface SystemStatusCardProps {
  level: SystemStatusLevel;
  issueCount: number;
  notes?: string[];
}

interface StatusConfig {
  color: string;
  icon: React.ReactNode;
  label: string;
}

function statusConfig(level: SystemStatusLevel): StatusConfig {
  switch (level) {
    case "healthy":
      return {
        color: "green",
        icon: <IconCircleCheck size={20} />,
        label: "All systems healthy",
      };
    case "warning":
      return {
        color: "yellow",
        icon: <IconAlertTriangle size={20} />,
        label: "Warnings detected",
      };
    case "action_needed":
      return {
        color: "red",
        icon: <IconCircleX size={20} />,
        label: "Action needed",
      };
    case "starting":
      return {
        color: "blue",
        icon: <IconLoader size={20} />,
        label: "Starting up",
      };
    default:
      return {
        color: "gray",
        icon: <IconQuestionMark size={20} />,
        label: "Status unknown",
      };
  }
}

export function SystemStatusCard({
  level,
  issueCount,
  notes,
}: SystemStatusCardProps) {
  const cfg = statusConfig(level);

  return (
    <Paper withBorder radius="md" p="sm">
      <Group gap="sm">
        <ThemeIcon color={cfg.color} variant="light" size="md" radius="xl">
          {cfg.icon}
        </ThemeIcon>
        <div>
          <Text size="sm" fw={700} c={cfg.color}>
            {cfg.label}
          </Text>
          {issueCount > 0 && (
            <Text size="xs" c="dimmed">
              {issueCount} {issueCount === 1 ? "issue" : "issues"} detected
            </Text>
          )}
          {notes?.map((n) => (
            <Text key={n} size="xs" c="dimmed">
              {n}
            </Text>
          ))}
        </div>
      </Group>
    </Paper>
  );
}
