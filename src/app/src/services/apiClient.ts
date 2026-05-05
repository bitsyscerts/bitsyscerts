/** Typed fetch wrapper for the bitsyscerts API. */

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function buildUrl(path: string): string {
  const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalised}`;
}

export async function apiFetch<T>(
  path: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): Promise<T> {
  const url = new URL(buildUrl(path), window.location.origin);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `API error ${String(response.status)}: ${response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}
