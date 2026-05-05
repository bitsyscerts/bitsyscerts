import { Badge, Divider, Group, SimpleGrid, Stack, Text } from "@mantine/core";
import type { HostnameResult } from "@/types";
import { DetailField } from "./DetailField";
import { formatDate } from "@/utils/format";

interface HostnameDetailBodyProps {
  item: HostnameResult;
}

/**
 * Scrollable body for a HostnameResult in the detail drawer, rendered in a
 * responsive SimpleGrid with labeled fields grouped by concern.
 */
export function HostnameDetailBody({ item }: HostnameDetailBodyProps) {
  return (
    <Stack gap="lg" p="md">
      <Stack gap="xs">
        <Group gap="xs">
          {item.is_wildcard && (
            <Badge color="brand" size="sm">
              Wildcard
            </Badge>
          )}
        </Group>
        <DetailField label="Hostname" value={item.hostname} mono />
        <DetailField
          label="Registrable Domain"
          value={item.registrable_domain}
          mono
        />
      </Stack>

      <Divider
        label={
          <Text size="xs" fw={500}>
            CT Observation
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField
          label="First Seen"
          value={formatDate(item.first_seen_ct)}
        />
        <DetailField label="Last Seen" value={formatDate(item.last_seen_ct)} />
      </SimpleGrid>

      <Divider
        label={
          <Text size="xs" fw={500}>
            Latest Certificate Window
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField
          label="Not Before"
          value={formatDate(item.latest_cert_not_before)}
        />
        <DetailField
          label="Not After"
          value={formatDate(item.latest_cert_not_after)}
        />
      </SimpleGrid>
    </Stack>
  );
}
