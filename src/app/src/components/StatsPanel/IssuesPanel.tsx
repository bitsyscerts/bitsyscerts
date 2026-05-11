import { Alert, Stack, Text } from "@mantine/core";
import { IconCircleCheck } from "@tabler/icons-react";
import type { DerivedIssue } from "@/utils/deriveSystemStatus";

interface IssuesPanelProps {
  issues: DerivedIssue[];
}

function IssueRow({ issue }: { issue: DerivedIssue }) {
  const color = issue.severity === "action_needed" ? "red" : "yellow";
  return (
    <Alert color={color} variant="light" py="xs" px="sm">
      <Text size="sm">{issue.message}</Text>
    </Alert>
  );
}

export function IssuesPanel({ issues }: IssuesPanelProps) {
  if (issues.length === 0) {
    return (
      <Alert
        color="green"
        variant="light"
        icon={<IconCircleCheck size={16} />}
        py="xs"
      >
        <Text size="sm">No action needed.</Text>
      </Alert>
    );
  }

  return (
    <Stack gap="xs">
      {issues.map((issue, idx) => (
        // Key on message text is safe: messages are distinct within a snapshot.
        <IssueRow key={`${issue.severity}-${String(idx)}`} issue={issue} />
      ))}
    </Stack>
  );
}
