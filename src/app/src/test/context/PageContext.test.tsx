import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PageProvider, usePageContext } from "@/context/PageContext";
import type { ReactNode } from "react";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter initialEntries={["/hosts"]}>
      <PageProvider>{children}</PageProvider>
    </MemoryRouter>
  );
}

describe("PageContext", () => {
  it("derives hosts as active page from /hosts URL", () => {
    const { result } = renderHook(() => usePageContext(), { wrapper });
    expect(result.current.activePage).toBe("hosts");
  });

  it("provides setActivePage function", () => {
    const { result } = renderHook(() => usePageContext(), { wrapper });
    expect(typeof result.current.setActivePage).toBe("function");
  });

  it("calls setActivePage without throwing", () => {
    const { result } = renderHook(() => usePageContext(), { wrapper });
    expect(() => {
      act(() => {
        result.current.setActivePage("stats");
      });
    }).not.toThrow();
  });

  it("throws when used outside PageProvider", async () => {
    const consoleSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const suppressWindowError = (e: ErrorEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    window.addEventListener("error", suppressWindowError, { capture: true });

    expect(() => {
      renderHook(() => usePageContext(), {
        wrapper: ({ children }: { children: ReactNode }) => (
          <MemoryRouter>{children}</MemoryRouter>
        ),
      });
    }).toThrow("usePageContext must be used inside PageProvider");

    await new Promise<void>((resolve) => {
      setTimeout(resolve, 0);
    });

    window.removeEventListener("error", suppressWindowError, { capture: true });
    consoleSpy.mockRestore();
  });
});
