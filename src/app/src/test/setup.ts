import "@testing-library/jest-dom";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { URL as NodeURL } from "node:url";

// Cleanup DOM after each test to prevent memory accumulation.
afterEach(() => {
  cleanup();
});

// React Router v7 (BrowserRouter) calls `new window.URL(...)` internally.
// jsdom replaces window.URL with a Web IDL wrapper that is not a usable
// constructor in forked worker processes (CI).  Override it with Node's
// built-in URL so react-router can construct URL objects during rendering.
// Importing from "node:url" escapes the jsdom scope and gives us the real
// Node.js constructor, unlike the bare `URL` identifier which resolves to
// the same jsdom wrapper.
window.URL = NodeURL as typeof globalThis.URL;

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
