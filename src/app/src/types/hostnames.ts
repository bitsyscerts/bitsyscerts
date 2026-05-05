/** Mirrors certsapi/hostnames/models.py — keep in sync with backend. */

export type SortField =
  | "not_before_asc"
  | "not_before_desc"
  | "not_after_asc"
  | "not_after_desc";

export const SORT_FIELD_LABELS: Record<SortField, string> = {
  not_before_asc: "Not Before ↑",
  not_before_desc: "Not Before ↓",
  not_after_asc: "Not After ↑",
  not_after_desc: "Not After ↓",
};

export interface HostnameSearchParams {
  q: string;
  recursive: boolean;
  depth: number | null;
  sort: SortField;
  limit: number;
  cursor: string | null;
  include_certs: boolean;
}

export interface CertEmbedResponse {
  fingerprint_sha256: string;
  spki_sha256: string;
  not_before: string;
  not_after: string;
  issuer_dn: string;
  issuer_common_name: string | null;
  issuer_organization: string | null;
  subject_common_name: string | null;
  is_wildcard_present: boolean;
  is_precertificate: boolean;
  subject_alternative_names: string[];
}

export interface HostnameResult {
  id: string;
  hostname: string;
  registrable_domain: string;
  is_wildcard: boolean;
  first_seen_ct: string | null;
  last_seen_ct: string | null;
  latest_cert_not_before: string | null;
  latest_cert_not_after: string | null;
  latest_cert: CertEmbedResponse | null;
}

export interface HostnameListResponse {
  items: HostnameResult[];
  next_cursor: string | null;
  total_returned: number;
  /** Only present on the first page. ≥10,001 means "more than 10,000". */
  total_estimate: number | null;
}

export const DEFAULT_HOSTNAME_SEARCH_PARAMS: Omit<HostnameSearchParams, "q"> = {
  recursive: true,
  depth: null,
  sort: "not_before_desc",
  limit: 5,
  cursor: null,
  include_certs: false,
};
