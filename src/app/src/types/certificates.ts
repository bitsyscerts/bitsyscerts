/** Mirrors certsapi/certificates/models.py — keep in sync with backend. */

export interface CertificateResponse {
  id: string;
  fingerprint_sha256: string;
  spki_sha256: string;
  serial_number: string;
  issuer_dn: string;
  issuer_common_name: string | null;
  issuer_organization: string | null;
  subject_dn: string;
  subject_common_name: string | null;
  not_before: string;
  not_after: string;
  signature_algorithm_oid: string;
  signature_algorithm_name: string;
  public_key_algorithm_oid: string;
  public_key_algorithm_name: string;
  public_key_bits_or_curve: string | null;
  is_precertificate: boolean;
  is_wildcard_present: boolean;
  san_count: number;
  first_seen_ct: string | null;
  last_seen_ct: string | null;
  subject_alternative_names: string[];
}
