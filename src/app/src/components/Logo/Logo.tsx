import { useComputedColorScheme } from "@mantine/core";
import { Group, Text, Image } from "@mantine/core";
import { Link } from "react-router-dom";
import logoLight from "@/assets/icon_forlight.png";
import logoDark from "@/assets/icon_fordark.png";

/**
 * Renders the bitsyscerts logo: square icon (light/dark aware) + wordmark text.
 * Wrapped in a react-router Link so clicking navigates to the dashboard.
 */
export function Logo() {
  const colorScheme = useComputedColorScheme("light");
  const isDark = colorScheme === "dark";
  const src = isDark ? logoDark : logoLight;

  return (
    <Link
      to="/"
      aria-label="Go to BitsysCerts dashboard"
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <Group gap="xs" align="center" wrap="nowrap">
        <Image src={src} alt="bitsyscerts logo" w={32} h={32} fit="contain" />
        <Text
          fw={700}
          size="lg"
          style={{ letterSpacing: "-0.02em", whiteSpace: "nowrap" }}
        >
          BitsysCerts
        </Text>
      </Group>
    </Link>
  );
}
