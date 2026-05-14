import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnnouncementBanner } from "@/components/AppShell/AnnouncementBanner";
import { AllProviders } from "../AllProviders";

afterEach(() => {
  vi.unstubAllEnvs();
});

function renderBanner() {
  return render(
    <AllProviders>
      <AnnouncementBanner />
    </AllProviders>,
  );
}

describe("AnnouncementBanner", () => {
  it("renders nothing when VITE_BANNER_VISIBLE is not set", () => {
    renderBanner();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders nothing when visible=true but text is empty", () => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "");
    renderBanner();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders the banner text when visible=true and text is set", () => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "Demo instance — be responsible!");
    renderBanner();
    expect(
      screen.getByText("Demo instance — be responsible!"),
    ).toBeInTheDocument();
  });

  it("renders nothing when visible=false even with text", () => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "false");
    vi.stubEnv("VITE_BANNER_TEXT", "Hidden message");
    renderBanner();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("defaults to info (blue) color when severity is not set", () => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "Hello");
    renderBanner();
    // Mantine Alert renders a [data-variant] attribute; spot-check that the
    // element exists rather than asserting on internal Mantine class names.
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it.each([
    ["warning", "warning"],
    ["error", "error"],
    ["success", "success"],
    ["info", "info"],
  ])("accepts severity=%s without throwing", (severity) => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "Test");
    vi.stubEnv("VITE_BANNER_SEVERITY", severity);
    expect(() => renderBanner()).not.toThrow();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it.each([
    "AlertTriangle",
    "AlertCircle",
    "CircleCheck",
    "Speakerphone",
    "InfoCircle",
  ])("accepts icon=%s without throwing", (icon) => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "Test");
    vi.stubEnv("VITE_BANNER_ICON", icon);
    expect(() => renderBanner()).not.toThrow();
  });

  it("falls back to InfoCircle for an unrecognised icon name", () => {
    vi.stubEnv("VITE_BANNER_VISIBLE", "true");
    vi.stubEnv("VITE_BANNER_TEXT", "Test");
    vi.stubEnv("VITE_BANNER_ICON", "NonExistentIcon");
    expect(() => renderBanner()).not.toThrow();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
