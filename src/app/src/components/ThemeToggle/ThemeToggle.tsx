import { ActionIcon, Tooltip } from "@mantine/core";
import { IconSun, IconMoon, IconDeviceDesktop } from "@tabler/icons-react";
import { useColorScheme } from "@/hooks/useColorScheme";
import type { ColorSchemeValue } from "@/context/ColorSchemeContext";

const ICON_MAP: Record<
  ColorSchemeValue,
  { icon: React.ReactNode; label: string }
> = {
  system: { icon: <IconDeviceDesktop size={18} />, label: "Theme: System" },
  light: { icon: <IconSun size={18} />, label: "Theme: Light" },
  dark: { icon: <IconMoon size={18} />, label: "Theme: Dark" },
};

/**
 * Single icon-only button that cycles System → Light → Dark on each click.
 * Shows the icon for the current scheme; no text displayed.
 */
export function ThemeToggle() {
  const { colorScheme, cycleScheme } = useColorScheme();
  const { icon, label } = ICON_MAP[colorScheme];

  return (
    <Tooltip label={label} position="bottom-end" withArrow>
      <ActionIcon
        variant="subtle"
        size="lg"
        onClick={cycleScheme}
        aria-label={label}
      >
        {icon}
      </ActionIcon>
    </Tooltip>
  );
}
