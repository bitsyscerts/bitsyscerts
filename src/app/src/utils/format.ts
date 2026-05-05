/** Shared formatting utilities for dates, fingerprints, and numbers. */

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
});

const NUMBER_FORMAT = new Intl.NumberFormat("en-US");

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return DATE_FORMAT.format(new Date(iso));
  } catch {
    return iso;
  }
}

export function truncateFingerprint(hex: string, chars = 16): string {
  return `${hex.slice(0, chars)}…`;
}

export function formatNumber(n: number): string {
  return NUMBER_FORMAT.format(n);
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function isCertExpired(notAfterIso: string | null | undefined): boolean {
  if (!notAfterIso) return false;
  return new Date(notAfterIso) < new Date();
}
