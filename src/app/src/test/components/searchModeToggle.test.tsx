import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MantineProvider } from "@mantine/core";
import type { ReactNode } from "react";
import { SearchModeToggle } from "@/components/SearchOptions/SearchModeToggle";

function wrapper({ children }: { children: ReactNode }) {
  return <MantineProvider>{children}</MantineProvider>;
}

describe("SearchModeToggle", () => {
  it("renders both mode options", () => {
    render(<SearchModeToggle value="hostnames" onChange={vi.fn()} />, {
      wrapper,
    });
    expect(screen.getByText("Hostnames")).toBeInTheDocument();
    expect(screen.getByText("Certificates")).toBeInTheDocument();
  });

  it("calls onChange with the selected value when clicking an option", () => {
    const onChange = vi.fn();
    render(<SearchModeToggle value="hostnames" onChange={onChange} />, {
      wrapper,
    });
    fireEvent.click(screen.getByText("Certificates"));
    expect(onChange).toHaveBeenCalledWith("certificates");
  });
});
