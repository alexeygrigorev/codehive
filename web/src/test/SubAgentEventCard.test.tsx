import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SubAgentEventCard from "@/components/SubAgentEventCard";

describe("SubAgentEventCard", () => {
  it("renders spawned card with child name, engine, and mission", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.spawned"
          childName="subagent-swe"
          childSessionId="child-1"
          engine="claude_code"
          mission="Add health check endpoint"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Spawned sub-agent/)).toBeInTheDocument();
    expect(screen.getByText("subagent-swe")).toBeInTheDocument();
    expect(
      container.querySelector(".subagent-card-engine"),
    ).toHaveTextContent("claude_code");
    expect(
      container.querySelector(".subagent-card-mission"),
    ).toHaveTextContent("Mission: Add health check endpoint");
  });

  it("renders report card with status, summary, and files changed", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.report"
          childName="subagent-swe"
          childSessionId="child-1"
          status="completed"
          summary="Added GET /health endpoint, 2 files changed, 2 tests passing"
          filesChanged={2}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Sub-agent completed/)).toBeInTheDocument();
    expect(screen.getByText("subagent-swe")).toBeInTheDocument();
    expect(
      container.querySelector(".subagent-card-summary"),
    ).toHaveTextContent(
      "Added GET /health endpoint, 2 files changed, 2 tests passing",
    );
    expect(
      container.querySelector(".subagent-card-status"),
    ).toHaveTextContent("Status: completed, 2 files changed");
  });

  it("renders clickable link to child session", () => {
    render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.spawned"
          childName="subagent-swe"
          childSessionId="child-1"
          engine="native"
          mission="Fix tests"
        />
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "subagent-swe" });
    expect(link).toHaveAttribute("href", "/sessions/child-1");
  });

  it("renders without link when childSessionId is not provided", () => {
    render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.spawned"
          childName="subagent-swe"
          engine="native"
          mission="Fix tests"
        />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("subagent-swe")).toBeInTheDocument();
  });

  it("sets data-event-type attribute on the card", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.spawned"
          childName="test"
        />
      </MemoryRouter>,
    );

    const card = container.querySelector(".subagent-event-card");
    expect(card).not.toBeNull();
    expect(card!.getAttribute("data-event-type")).toBe("subagent.spawned");
  });

  it("applies green border for completed report", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.report"
          childName="test"
          status="completed"
          summary="Done"
        />
      </MemoryRouter>,
    );

    const card = container.querySelector(".subagent-event-card");
    expect(card!.className).toContain("border-green-400");
  });

  it("applies red border for failed report", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.report"
          childName="test"
          status="failed"
          summary="Error occurred"
        />
      </MemoryRouter>,
    );

    const card = container.querySelector(".subagent-event-card");
    expect(card!.className).toContain("border-red-400");
  });

  it("does not show mission for report events", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.report"
          childName="test"
          mission="This should not show"
          status="completed"
          summary="Done"
        />
      </MemoryRouter>,
    );

    expect(container.querySelector(".subagent-card-mission")).toBeNull();
  });

  it("does not show summary for spawned events", () => {
    const { container } = render(
      <MemoryRouter>
        <SubAgentEventCard
          eventType="subagent.spawned"
          childName="test"
          summary="This should not show"
          mission="Real mission"
        />
      </MemoryRouter>,
    );

    expect(container.querySelector(".subagent-card-summary")).toBeNull();
  });
});
