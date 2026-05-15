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
 * Controlled by runtime environment variables injected by docker-entrypoint.sh
 * into window.__ENV__ at container startup (Docker Compose deployments), or by
 * VITE_BANNER_* variables read by the Vite dev server (developer mode).
 * Returns null when the banner is not visible or the text is empty.
 *
 * Docker Compose vars (set in .env, no rebuild required):
 *   BANNER_VISIBLE   "true" to show the banner; anything else hides it.
 *   BANNER_TEXT      The message to display.
 *   BANNER_ICON      Icon name (without "Icon" prefix).
 *                    Supported: InfoCircle (default), AlertTriangle,
 *                    AlertCircle, CircleCheck, Speakerphone.
 *   BANNER_SEVERITY  Alert color: info (default), warning, error, success.
 *
 * Developer mode equivalents (prefix with VITE_ in .env):
 *   VITE_BANNER_VISIBLE, VITE_BANNER_TEXT, VITE_BANNER_ICON, VITE_BANNER_SEVERITY
 */
export function AnnouncementBanner() {
  const env = window.__ENV__ ?? {};
  const visible =
    (env.BANNER_VISIBLE ?? import.meta.env.VITE_BANNER_VISIBLE) === "true";
  const text = env.BANNER_TEXT ?? import.meta.env.VITE_BANNER_TEXT ?? "";

  if (!visible || !text) return null;

  const icon = resolveIcon(
    env.BANNER_ICON ?? import.meta.env.VITE_BANNER_ICON ?? "",
  );
  const color = resolveColor(
    env.BANNER_SEVERITY ?? import.meta.env.VITE_BANNER_SEVERITY ?? "",
  );

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
