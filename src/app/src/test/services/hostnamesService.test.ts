import { describe, it, expect, vi } from "vitest";
import {
  searchHostnames,
  HOSTNAME_QUERY_KEYS,
} from "@/services/hostnamesService";

vi.mock("@/services/apiClient", () => ({
  apiFetch: vi.fn().mockResolvedValue({ items: [], next_cursor: null }),
}));

import { apiFetch } from "@/services/apiClient";
const mockApiFetch = vi.mocked(apiFetch);

const BASE_PARAMS = {
  q: "example.com",
  recursive: true,
  depth: null,
  sort: "not_before_desc" as const,
  limit: 50,
  cursor: null,
  include_certs: false,
};

describe("HOSTNAME_QUERY_KEYS", () => {
  it("returns a stable key array for search", () => {
    const key = HOSTNAME_QUERY_KEYS.search(BASE_PARAMS);
    expect(key[0]).toBe("hostnames");
    expect(key[1]).toBe("search");
    expect(key[2]).toEqual(BASE_PARAMS);
  });
});

describe("searchHostnames", () => {
  it("calls apiFetch with the correct path and core params", async () => {
    await searchHostnames(BASE_PARAMS);
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/v1/hostnames",
      expect.objectContaining({
        q: "example.com",
        recursive: true,
        sort: "not_before_desc",
        limit: 50,
      }),
    );
  });

  it("omits depth when null", async () => {
    await searchHostnames({ ...BASE_PARAMS, depth: null });
    const params = mockApiFetch.mock.calls.at(-1)?.[1];
    expect(params?.depth).toBeUndefined();
  });

  it("includes depth when set", async () => {
    await searchHostnames({ ...BASE_PARAMS, depth: 3 });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/v1/hostnames",
      expect.objectContaining({ depth: 3 }),
    );
  });

  it("omits cursor when null", async () => {
    await searchHostnames({ ...BASE_PARAMS, cursor: null });
    const params = mockApiFetch.mock.calls.at(-1)?.[1];
    expect(params?.cursor).toBeUndefined();
  });

  it("includes cursor when set", async () => {
    await searchHostnames({ ...BASE_PARAMS, cursor: "cursor-abc" });
    expect(mockApiFetch).toHaveBeenCalledWith(
      "/v1/hostnames",
      expect.objectContaining({ cursor: "cursor-abc" }),
    );
  });
});
