import { Badge, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconChevronRight } from "@tabler/icons-react";
import type { CertEmbedResponse } from "@/types";
import { formatDate, truncateFingerprint } from "@/utils/format";

interface CertEmbedRowProps {
  cert: CertEmbedResponse;
  onClick?: (cert: CertEmbedResponse) => void;
}

/**
 * Renders the embedded certificate fields beneath a hostname result row.
 * When onClick is provided the row is independently clickable and stops
 * propagation so the parent hostname card does not also open.
 */
export function CertEmbedRow({ cert, onClick }: CertEmbedRowProps) {
  const issuer =
    cert.issuer_common_name ?? cert.issuer_organization ?? cert.issuer_dn;

  function handleClick(e: React.MouseEvent) {
    e.stopPropagation();
    onClick?.(cert);
  }

  const content = (
    <Stack
      gap={4}
      mt={6}
      pl="sm"
      py={4}
      pr={4}
      style={{
        borderLeft: "2px solid var(--mantine-color-brand-4)",
        borderRadius: "0 4px 4px 0",
      }}
    >
      <Group gap="xs" wrap="nowrap" justify="space-between">
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <Text size="xs" c="dimmed" ff="monospace" truncate>
            {truncateFingerprint(cert.fingerprint_sha256)}
          </Text>
          {cert.is_wildcard_present && (
            <Badge size="xs" color="brand">
              wildcard
            </Badge>
          )}
          {cert.is_precertificate && (
            <Badge size="xs" color="gray">
              pre-cert
            </Badge>
          )}
        </Group>
        {onClick && (
          <IconChevronRight size={12} style={{ flexShrink: 0, opacity: 0.4 }} />
        )}
      </Group>
      <Text size="xs" c="dimmed">
        {issuer}
      </Text>
      <Text size="xs" c="dimmed">
        {formatDate(cert.not_before)} → {formatDate(cert.not_after)}
      </Text>
    </Stack>
  );

  if (!onClick) {
    return content;
  }

  return (
    <UnstyledButton
      w="100%"
      onClick={handleClick}
      aria-label="Open embedded certificate details"
      style={{ cursor: "pointer" }}
    >
      {content}
    </UnstyledButton>
  );
}
