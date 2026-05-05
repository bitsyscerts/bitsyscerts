import { apiFetch } from "./apiClient";
import type { HostnameListResponse, HostnameSearchParams } from "@/types";

export const HOSTNAME_QUERY_KEYS = {
  search: (params: HostnameSearchParams) =>
    ["hostnames", "search", params] as const,
} as const;

type SearchApiParams = Record<
  string,
  string | number | boolean | null | undefined
>;

function buildSearchParams(params: HostnameSearchParams): SearchApiParams {
  return {
    q: params.q,
    recursive: params.recursive,
    sort: params.sort,
    limit: params.limit,
    depth: params.depth ?? undefined,
    cursor: params.cursor ?? undefined,
    include_certs: params.include_certs,
  };
}

export async function searchHostnames(
  params: HostnameSearchParams,
): Promise<HostnameListResponse> {
  return apiFetch<HostnameListResponse>(
    "/v1/hostnames",
    buildSearchParams(params),
  );
}
