import {
  Anchor,
  Divider,
  Group,
  Image,
  Modal,
  Stack,
  Text,
  useComputedColorScheme,
} from "@mantine/core";
import {
  IconBrandGithub,
  IconInfoCircle,
  IconWorld,
} from "@tabler/icons-react";
import logoLight from "@/assets/icon_forlight.png";
import logoDark from "@/assets/icon_fordark.png";

interface AboutModalProps {
  version: string;
  opened: boolean;
  onClose: () => void;
}

/**
 * Logo + wordmark used inside the About modal body.
 * Needs its own component so useComputedColorScheme runs inside MantineProvider.
 */
function AboutLogo() {
  const colorScheme = useComputedColorScheme("light");
  const src = colorScheme === "dark" ? logoDark : logoLight;
  return (
    <Group gap="sm" justify="center" align="center">
      <Image src={src} alt="BitsysCerts logo" w={48} h={48} fit="contain" />
      <Text fw={700} size="xl" style={{ letterSpacing: "-0.02em" }}>
        BitsysCerts
      </Text>
    </Group>
  );
}

/**
 * "About BitsysCerts" modal opened by clicking the version string in the
 * footer. Shows the logo, version, and links to GitHub and the website.
 */
export function AboutModal({ version, opened, onClose }: AboutModalProps) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="xs" align="center">
          <IconInfoCircle size={18} />
          <Text fw={600} size="sm">
            About BitsysCerts
          </Text>
        </Group>
      }
      size="xs"
      centered
    >
      <Stack gap="md" pb="xs">
        <AboutLogo />
        <Text size="sm" c="dimmed" ta="center">
          {`v${version}`}
        </Text>
        <Divider />
        <Stack gap="xs">
          <Anchor
            href="https://github.com/bitsyscerts/"
            target="_blank"
            rel="noopener noreferrer"
            size="sm"
          >
            <Group gap="xs" align="center">
              <IconBrandGithub size={16} />
              github.com/bitsyscerts
            </Group>
          </Anchor>
          <Anchor
            href="https://bitsyscerts.com/"
            target="_blank"
            rel="noopener noreferrer"
            size="sm"
          >
            <Group gap="xs" align="center">
              <IconWorld size={16} />
              bitsyscerts.com
            </Group>
          </Anchor>
        </Stack>
      </Stack>
    </Modal>
  );
}
