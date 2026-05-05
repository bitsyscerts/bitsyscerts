import { useMantineColorScheme } from "@mantine/core";
import { Group, Text, Image } from "@mantine/core";
import logoLight from "@/assets/icon_forlight.png";
import logoDark from "@/assets/icon_fordark.png";

/**
 * Renders the bitsyscerts logo: square icon (light/dark aware) + wordmark text.
 * Drop icon_forlight.png and icon_fordark.png into src/assets/ to activate.
 */
export function Logo() {
  const { colorScheme } = useMantineColorScheme();
  const isDark = colorScheme === "dark";
  const src = isDark ? logoDark : logoLight;

  return (
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
  );
}
