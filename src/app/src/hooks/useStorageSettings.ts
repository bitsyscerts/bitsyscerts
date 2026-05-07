import { useQuery } from "@tanstack/react-query";
import {
  getStorageSettings,
  SETTINGS_QUERY_KEYS,
} from "@/services/settingsApi";
import type { StorageSettingsResponse } from "@/types/settings";

/**
 * TanStack Query hook for reading active storage settings.
 *
 * @param refetchInterval - milliseconds between automatic refetches (default 120 s).
 */
export function useStorageSettings(refetchInterval = 120_000) {
  return useQuery<StorageSettingsResponse>({
    queryKey: SETTINGS_QUERY_KEYS.storageSettings,
    queryFn: getStorageSettings,
    refetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });
}
