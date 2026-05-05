import { Button, Container, Stack, Text, Title } from "@mantine/core";
import { IconArrowLeft, IconCertificate } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";

/**
 * Branded 404 page shown when the URL doesn't match any known route.
 * Allows the user to return to the Hosts search page.
 */
export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <Container size="xs" py="xl">
      <Stack align="center" gap="lg" mt="xl">
        <IconCertificate
          size={64}
          style={{ color: "var(--mantine-color-brand-filled)", opacity: 0.7 }}
        />

        <Stack align="center" gap="xs">
          <Title
            order={1}
            style={{
              fontSize: "6rem",
              fontWeight: 900,
              lineHeight: 1,
              color: "var(--mantine-color-brand-filled)",
            }}
          >
            404
          </Title>
          <Title order={3} fw={600}>
            Page not found
          </Title>
          <Text c="dimmed" ta="center" maw={320}>
            This route doesn't exist. If you bookmarked it, it may have moved or
            never existed.
          </Text>
        </Stack>

        <Button
          leftSection={<IconArrowLeft size={16} />}
          variant="light"
          color="brand"
          onClick={() => navigate("/hosts")}
        >
          Back to Hosts
        </Button>
      </Stack>
    </Container>
  );
}
