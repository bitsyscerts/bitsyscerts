import { Badge } from "@mantine/core";
import type { ProjectionConfidence } from "@/types";

interface ProjectionConfidenceBadgeProps {
  confidence: ProjectionConfidence | null | undefined;
}

const CONFIDENCE_LABEL: Record<ProjectionConfidence, string> = {
  low: "Low confidence",
  medium: "Medium confidence",
  high: "High confidence",
};

const CONFIDENCE_COLOR: Record<ProjectionConfidence, string> = {
  low: "red",
  medium: "yellow",
  high: "green",
};

export function ProjectionConfidenceBadge({
  confidence,
}: ProjectionConfidenceBadgeProps) {
  if (confidence == null) return null;
  return (
    <Badge
      variant="light"
      color={CONFIDENCE_COLOR[confidence]}
      aria-label={`Projection confidence: ${CONFIDENCE_LABEL[confidence]}`}
    >
      {CONFIDENCE_LABEL[confidence]}
    </Badge>
  );
}
