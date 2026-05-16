/** Typed fetch wrapper for the bitsyscerts API. */

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

const FETCH_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ApiTimeoutError extends Error {
  public readonly code = "query_timeout" as const;

  constructor() {
    super("Request timed out");
    this.name = "ApiTimeoutError";
  }
}

function buildUrl(path: string): string {
  const base = API_BASE.endsWith("/") ? API_BASE.slice(0, -1) : API_BASE;
  const normalised = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalised}`;
}

async function _fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new ApiError(
      response.status,
      `API error ${String(response.status)}: ${response.statusText}`,
    );
  }
  return response.json() as Promise<T>;
}

async function _withTimeout<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  ms: number,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, ms);
  try {
    return await fn(controller.signal);
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new ApiTimeoutError();
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
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
  return _withTimeout(
    (signal) => _fetchJson<T>(url.toString(), signal),
    FETCH_TIMEOUT_MS,
  );
}

export async function apiMutate<T>(
  path: string,
  body: unknown,
  method: "PUT" | "POST" = "PUT",
): Promise<T> {
  const url = new URL(buildUrl(path), window.location.origin);

  const response = await fetch(url.toString(), {
    method,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `API error ${String(response.status)}: ${response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}
