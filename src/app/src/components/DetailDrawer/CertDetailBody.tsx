import { Badge, Divider, Group, SimpleGrid, Stack, Text } from "@mantine/core";
import type { CertificateResponse } from "@/types";
import { DetailField } from "./DetailField";
import { SanList } from "./SanList";
import { formatDate } from "@/utils/format";

interface CertDetailBodyProps {
  cert: CertificateResponse;
}

/**
 * Scrollable body for a CertificateResponse in the detail drawer.
 * Fields are grouped into sections: identity, issuer, validity, crypto, CT, SANs.
 */
export function CertDetailBody({ cert }: CertDetailBodyProps) {
  return (
    <Stack gap="lg" p="md">
      <Stack gap="xs">
        <Group gap="xs">
          {cert.is_wildcard_present && (
            <Badge color="brand" size="sm">
              Wildcard
            </Badge>
          )}
          {cert.is_precertificate && (
            <Badge color="gray" size="sm">
              Pre-certificate
            </Badge>
          )}
        </Group>
        <DetailField label="Subject CN" value={cert.subject_common_name} />
        <DetailField label="Subject DN" value={cert.subject_dn} mono />
        <DetailField label="Serial Number" value={cert.serial_number} mono />
      </Stack>

      <Divider
        label={
          <Text size="xs" fw={500}>
            Issuer
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField label="Common Name" value={cert.issuer_common_name} />
        <DetailField label="Organization" value={cert.issuer_organization} />
      </SimpleGrid>
      <DetailField label="Issuer DN" value={cert.issuer_dn} mono />

      <Divider
        label={
          <Text size="xs" fw={500}>
            Validity
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField label="Not Before" value={formatDate(cert.not_before)} />
        <DetailField label="Not After" value={formatDate(cert.not_after)} />
      </SimpleGrid>

      <Divider
        label={
          <Text size="xs" fw={500}>
            Cryptography
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField
          label="Signature Algorithm"
          value={cert.signature_algorithm_name}
        />
        <DetailField
          label="Public Key Algorithm"
          value={cert.public_key_algorithm_name}
        />
        <DetailField
          label="Key Size / Curve"
          value={cert.public_key_bits_or_curve}
        />
        <DetailField label="SAN Count" value={String(cert.san_count)} />
      </SimpleGrid>

      <Divider
        label={
          <Text size="xs" fw={500}>
            Fingerprints
          </Text>
        }
        labelPosition="left"
      />
      <DetailField
        label="SHA-256 Fingerprint"
        value={cert.fingerprint_sha256}
        mono
      />
      <DetailField label="SPKI SHA-256" value={cert.spki_sha256} mono />

      <Divider
        label={
          <Text size="xs" fw={500}>
            CT Log Observation
          </Text>
        }
        labelPosition="left"
      />
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <DetailField
          label="First Seen"
          value={formatDate(cert.first_seen_ct)}
        />
        <DetailField label="Last Seen" value={formatDate(cert.last_seen_ct)} />
      </SimpleGrid>

      <Divider
        label={
          <Text size="xs" fw={500}>
            Subject Alternative Names
          </Text>
        }
        labelPosition="left"
      />
      <SanList sans={cert.subject_alternative_names} />
    </Stack>
  );
}
