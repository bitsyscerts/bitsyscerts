import { Alert, Text } from "@mantine/core";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconCircleCheck,
  IconInfoCircle,
  IconSpeakerphone,
} from "@tabler/icons-react";

/**
 * Operator-configurable site-wide announcement banner.
 *
 * Controlled entirely by VITE_BANNER_* environment variables so that demo
 * operators and self-hosters can display a notice without touching source
 * code. Returns null when VITE_BANNER_VISIBLE is not "true" or when the
 * text is empty.
 *
 * Env vars:
 *   VITE_BANNER_VISIBLE   "true" to show the banner; anything else hides it.
 *   VITE_BANNER_TEXT      The message to display.
 *   VITE_BANNER_ICON      Tabler icon name (without "Icon" prefix).
 *                         Supported: InfoCircle (default), AlertTriangle,
 *                         AlertCircle, CircleCheck, Speakerphone.
 *   VITE_BANNER_SEVERITY  Mantine Alert color: info (default), warning,
 *                         error, success.
 */
export function AnnouncementBanner() {
  const visible = import.meta.env.VITE_BANNER_VISIBLE === "true";
  const text = import.meta.env.VITE_BANNER_TEXT ?? "";

  if (!visible || !text) return null;

  const icon = resolveIcon(import.meta.env.VITE_BANNER_ICON ?? "");
  const color = resolveColor(import.meta.env.VITE_BANNER_SEVERITY ?? "");

  return (
    <Alert color={color} variant="light" icon={icon} radius={0} py="xs">
      <Text size="sm">{text}</Text>
    </Alert>
  );
}

function resolveIcon(name: string): React.ReactNode {
  switch (name.toLowerCase()) {
    case "alerttriangle":
      return <IconAlertTriangle size={16} />;
    case "alertcircle":
      return <IconAlertCircle size={16} />;
    case "circlecheck":
      return <IconCircleCheck size={16} />;
    case "speakerphone":
      return <IconSpeakerphone size={16} />;
    default:
      return <IconInfoCircle size={16} />;
  }
}

function resolveColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "warning":
      return "yellow";
    case "error":
      return "red";
    case "success":
      return "green";
    default:
      return "blue";
  }
}
