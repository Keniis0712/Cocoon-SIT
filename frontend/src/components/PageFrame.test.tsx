import { SidebarProvider } from "@/components/ui/sidebar";
import PageFrame from "@/components/PageFrame";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("PageFrame", () => {
  it("renders the page title, optional description, actions, and content", () => {
    render(
      <SidebarProvider>
        <PageFrame
          title="Workspace"
          description="Realtime workspace status"
          actions={<button type="button">Refresh</button>}
        >
          <div>Panel content</div>
        </PageFrame>
      </SidebarProvider>,
    );

    expect(screen.getByRole("heading", { name: "Workspace" })).toBeInTheDocument();
    expect(screen.getByText("Realtime workspace status")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
    expect(screen.getByText("Panel content")).toBeInTheDocument();
  });
});
