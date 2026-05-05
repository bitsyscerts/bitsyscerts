import { useEffect } from "react";
import {
  Alert,
  Button,
  Container,
  Group,
  Paper,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconAlertCircle, IconSearch } from "@tabler/icons-react";
import { useSearchParams } from "react-router-dom";
import { CertDetailBody } from "@/components/DetailDrawer/CertDetailBody";
import { useCertificate } from "@/hooks/useCertificate";
import { useCertStateContext } from "@/context/CertStateContext";

const SHA256_RE = /^[0-9a-f]{64}$/i;

function isValidFingerprint(value: string) {
  return SHA256_RE.test(value.trim());
}

/**
 * Certificate lookup page. Accepts a 64-character hex SHA-256 fingerprint and
 * shows the certificate detail inline. State is lifted above the router so
 * it survives navigation; the fingerprint is also persisted in the URL for
 * bookmarking.
 */
export function CertificatesContent() {
  const { input, submittedFp, setInput, submitLookup } = useCertStateContext();
  const [searchParams, setSearchParams] = useSearchParams();

  // On mount: restore from URL if context is empty and URL has a fingerprint.
  useEffect(() => {
    if (submittedFp) return;
    const urlFp = searchParams.get("fingerprint") ?? "";
    if (isValidFingerprint(urlFp)) submitLookup(urlFp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep URL in sync when the user submits a lookup.
  useEffect(() => {
    if (!submittedFp) return;
    setSearchParams({ fingerprint: submittedFp }, { replace: true });
  }, [submittedFp, setSearchParams]);

  const { data, isLoading, isError, error } = useCertificate(submittedFp);

  function handleSubmit() {
    const fp = input.trim();
    if (isValidFingerprint(fp)) submitLookup(fp);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSubmit();
  }

  const isInvalid = input.trim().length > 0 && !isValidFingerprint(input);

  return (
    <Container size="xl" py="md">
      <Stack gap="md">
        <Title order={4} c="dimmed" fw={400}>
          Look up a certificate by its SHA-256 fingerprint
        </Title>

        <Group gap="sm" align="flex-start" wrap="nowrap">
          <TextInput
            flex={1}
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. 3a4b5c… (64 hex characters)"
            error={isInvalid ? "Must be exactly 64 hex characters" : undefined}
            aria-label="SHA-256 certificate fingerprint"
          />
          <Button
            leftSection={<IconSearch size={16} />}
            onClick={handleSubmit}
            disabled={!isValidFingerprint(input)}
          >
            Look up
          </Button>
        </Group>

        {isLoading && submittedFp && (
          <Stack gap="sm">
            {Array.from({ length: 6 }).map((_, i) => (
              // biome-ignore lint: static skeleton list
              <Skeleton key={i} height={28} radius="sm" />
            ))}
          </Stack>
        )}

        {isError && (
          <Alert
            icon={<IconAlertCircle size={16} />}
            color="red"
            title="Certificate not found"
          >
            <Text size="sm">
              {error instanceof Error
                ? error.message
                : "An unexpected error occurred."}
            </Text>
          </Alert>
        )}

        {data && (
          <Paper p="md" radius="md" withBorder>
            <CertDetailBody cert={data} />
          </Paper>
        )}
      </Stack>
    </Container>
  );
}
