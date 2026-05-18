import type { StorageProjection } from "@/types";

export interface StorageCeiling {
  /** High-end projection bytes used as the display denominator. */
  ceilingBytes: number | null;
  /** Ratio of current DB size to ceilingBytes (0–1). Null when unavailable. */
  pct: number | null;
}

/**
 * Returns the storage ceiling (projection_high_bytes, falling back to the
 * mid-point estimate) and the ratio of actual DB size to that ceiling.
 *
 * Using the high-end estimate as the denominator means the percentage rises
 * toward 100% only if the worst-case projection is reached — under-promising
 * so the user is pleasantly surprised when actual storage lands lower.
 */
export function computeStorageCeiling(
  projection: StorageProjection,
): StorageCeiling {
  const ceilingBytes =
    projection.projection_high_bytes ??
    projection.projected_final_database_size_bytes;
  const pct =
    ceilingBytes != null && ceilingBytes > 0
      ? projection.database_size_bytes / ceilingBytes
      : (projection.storage_percent_of_projected ?? null);
  return { ceilingBytes, pct };
}
