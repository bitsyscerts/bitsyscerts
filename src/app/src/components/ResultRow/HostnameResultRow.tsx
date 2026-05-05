import {
  Badge,
  Group,
  Paper,
  Stack,
  Text,
  UnstyledButton,
} from "@mantine/core";
import type { CertEmbedResponse, HostnameResult } from "@/types";
import { CertEmbedRow } from "./CertEmbedRow";
import { formatDate, isCertExpired } from "@/utils/format";

interface HostnameResultRowProps {
  item: HostnameResult;
  onClick: (item: HostnameResult) => void;
  onCertClick?: (cert: CertEmbedResponse) => void;
}

/**
 * Renders one HostnameResult as a clickable card row. Shows hostname, domain,
 * wildcard badge, CT dates, and optionally the embedded CertEmbedRow.
 */
export function HostnameResultRow({
  item,
  onClick,
  onCertClick,
}: HostnameResultRowProps) {
  const expired = isCertExpired(item.latest_cert_not_after);

  return (
    <UnstyledButton
      w="100%"
      onClick={() => {
        onClick(item);
      }}
    >
      <Paper
        p="sm"
        radius="md"
        withBorder
        style={{ cursor: "pointer" }}
        className="result-row"
      >
        <Stack gap={4}>
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Text
              fw={600}
              size="sm"
              ff="monospace"
              style={{ wordBreak: "break-all" }}
            >
              {item.hostname}
            </Text>
            <Group gap={4} wrap="nowrap">
              {item.is_wildcard && (
                <Badge size="xs" color="brand">
                  wildcard
                </Badge>
              )}
              {expired && (
                <Badge size="xs" color="red">
                  expired
                </Badge>
              )}
            </Group>
          </Group>

          <Text size="xs" c="dimmed">
            {item.registrable_domain}
          </Text>

          <Group gap="xl" wrap="wrap">
            <Text size="xs" c="dimmed">
              First seen: {formatDate(item.first_seen_ct)}
            </Text>
            <Text size="xs" c="dimmed">
              Last seen: {formatDate(item.last_seen_ct)}
            </Text>
          </Group>

          {item.latest_cert && (
            <CertEmbedRow cert={item.latest_cert} onClick={onCertClick} />
          )}
        </Stack>
      </Paper>
    </UnstyledButton>
  );
}
