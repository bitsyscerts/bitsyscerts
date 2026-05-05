import "@testing-library/jest-dom";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Cleanup DOM after each test to prevent memory accumulation.
afterEach(() => {
  cleanup();
});

// jsdom does not implement matchMedia; polyfill it for Mantine and other consumers.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

// jsdom does not implement ResizeObserver; polyfill it for Mantine ScrollArea.
global.ResizeObserver = class ResizeObserver {
  observe() {
    return undefined;
  }
  unobserve() {
    return undefined;
  }
  disconnect() {
    return undefined;
  }
};
