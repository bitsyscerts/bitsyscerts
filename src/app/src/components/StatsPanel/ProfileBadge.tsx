import { Badge } from "@mantine/core";

interface ProfileBadgeProps {
  profile: string | null | undefined;
}

const PROFILE_LABEL: Record<string, string> = {
  lite: "Lite",
  standard: "Standard",
  research: "Research",
};

export function ProfileBadge({ profile }: ProfileBadgeProps) {
  if (profile == null) return null;
  const label = PROFILE_LABEL[profile] ?? profile;
  return (
    <Badge
      variant="light"
      color="blue"
      aria-label={`Storage profile: ${label}`}
    >
      {label}
    </Badge>
  );
}
