import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  updateStorageSettings,
  SETTINGS_QUERY_KEYS,
} from "@/services/settingsApi";
import { STATS_QUERY_KEYS } from "@/services/statsService";
import type {
  UpdateStorageSettingsRequest,
  UpdateStorageSettingsResult,
} from "@/types/settings";

/**
 * TanStack Query mutation hook for updating storage settings.
 *
 * On success, invalidates both the settings and stats caches so the UI
 * reflects the new active profile immediately.
 */
export function useUpdateStorageSettings() {
  const queryClient = useQueryClient();

  return useMutation<
    UpdateStorageSettingsResult,
    Error,
    UpdateStorageSettingsRequest
  >({
    mutationFn: updateStorageSettings,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: SETTINGS_QUERY_KEYS.storageSettings,
      });
      void queryClient.invalidateQueries({
        queryKey: STATS_QUERY_KEYS.stats(),
      });
    },
  });
}
