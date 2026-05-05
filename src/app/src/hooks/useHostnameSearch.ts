import { useQuery } from "@tanstack/react-query";
import {
  searchHostnames,
  HOSTNAME_QUERY_KEYS,
} from "@/services/hostnamesService";
import type { HostnameListResponse, HostnameSearchParams } from "@/types";

/**
 * TanStack Query wrapper for the hostname search endpoint.
 * Query is disabled when params.q is empty.
 */
export function useHostnameSearch(params: HostnameSearchParams) {
  return useQuery<HostnameListResponse>({
    queryKey: HOSTNAME_QUERY_KEYS.search(params),
    queryFn: () => searchHostnames(params),
    enabled: params.q.trim().length > 0,
  });
}
