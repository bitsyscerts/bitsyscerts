import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiError, apiFetch } from "@/services/apiClient";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
  mockFetch.mockReset();
});

describe("ApiError", () => {
  it("has correct name and status", () => {
    const err = new ApiError(404, "Not found");
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not found");
  });
});

describe("apiFetch", () => {
  it("returns parsed JSON on a successful response", async () => {
    const payload = { hello: "world" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(payload),
    });

    const result = await apiFetch<typeof payload>("/v1/test");
    expect(result).toEqual(payload);
  });

  it("passes query params to the URL", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/v1/hostnames", {
      q: "example.com",
      limit: 5,
      recursive: true,
    });

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("q=example.com");
    expect(calledUrl).toContain("limit=5");
    expect(calledUrl).toContain("recursive=true");
  });

  it("omits null and undefined params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({}),
    });

    await apiFetch("/v1/hostnames", {
      q: "test",
      cursor: null,
      depth: undefined,
    });

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("cursor");
    expect(calledUrl).not.toContain("depth");
  });

  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
    });

    await expect(apiFetch("/v1/missing")).rejects.toBeInstanceOf(ApiError);
  });

  it("includes the status code in the thrown ApiError", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Server Error",
    });

    const err = await apiFetch("/v1/broken").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
  });
});
