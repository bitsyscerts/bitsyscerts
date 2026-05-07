/** API calls for the storage settings endpoints. */

import { apiFetch, apiMutate } from "./apiClient";
import type {
  StorageSettingsHistoryItem,
  StorageSettingsResponse,
  UpdateStorageSettingsRequest,
  UpdateStorageSettingsResult,
} from "../types/settings";

export const SETTINGS_QUERY_KEYS = {
  storageSettings: ["settings", "storage"] as const,
  storageSettingsHistory: ["settings", "storage", "history"] as const,
};

export function getStorageSettings(): Promise<StorageSettingsResponse> {
  return apiFetch<StorageSettingsResponse>("/v1/settings/storage");
}

export function updateStorageSettings(
  request: UpdateStorageSettingsRequest,
): Promise<UpdateStorageSettingsResult> {
  return apiMutate<UpdateStorageSettingsResult>(
    "/v1/settings/storage",
    request,
    "PUT",
  );
}

export function getStorageSettingsHistory(): Promise<
  StorageSettingsHistoryItem[]
> {
  return apiFetch<StorageSettingsHistoryItem[]>("/v1/settings/storage/history");
}
