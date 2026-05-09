import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { AboutModal } from "@/components/AppShell/AboutModal";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

describe("AboutModal", () => {
  it("renders version, github link, and website link when opened", () => {
    render(<AboutModal version="1.2.3" opened onClose={vi.fn()} />, {
      wrapper,
    });
    expect(screen.getByText("About BitsysCerts")).toBeInTheDocument();
    expect(screen.getByText("v1.2.3")).toBeInTheDocument();
    const githubLink = screen.getByRole("link", {
      name: /github\.com\/bitsyscerts/i,
    });
    expect(githubLink).toHaveAttribute(
      "href",
      "https://github.com/bitsyscerts/",
    );
    const siteLink = screen.getByRole("link", { name: /bitsyscerts\.com/i });
    expect(siteLink).toHaveAttribute("href", "https://bitsyscerts.com/");
  });

  it("links open in a new tab with noopener", () => {
    render(<AboutModal version="dev" opened onClose={vi.fn()} />, { wrapper });
    for (const link of screen.getAllByRole("link")) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });

  it("does not render content when closed", () => {
    render(<AboutModal version="1.2.3" opened={false} onClose={vi.fn()} />, {
      wrapper,
    });
    expect(screen.queryByText("v1.2.3")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /github\.com\/bitsyscerts/i }),
    ).not.toBeInTheDocument();
  });
});
