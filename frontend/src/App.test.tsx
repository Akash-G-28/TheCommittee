import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const decision = {
  id: "11111111-1111-1111-1111-111111111111",
  question: "Should I buy the chair?",
  category: "purchase",
  context: "I work from home.",
  agent_roster: ["wallet", "future_me", "chaos"] as const,
  status: "RECEIVED",
  created_at: "2026-07-07T00:00:00Z",
  updated_at: "2026-07-07T00:00:00Z",
};

const opinions = (["wallet", "future_me", "chaos"] as const).map((agent, index) => ({
  id: `opinion-${agent}`,
  decision_id: decision.id,
  agent,
  vote: (index === 0 ? "NO" : "YES") as "NO" | "YES",
  confidence: 0.8,
  summary: `${agent} has considered the question.`,
  key_factors: ["cost", "time"],
  created_at: "2026-07-07T00:00:00Z",
}));

const detail = {
  decision: { ...decision, status: "VERDICT_READY" },
  opinions,
  rounds: [
    { round_number: 1, status: "COMPLETE" },
    { round_number: 2, status: "COMPLETE" },
  ],
  revised_opinions: opinions.map((item) => ({
    id: `revision-${item.agent}`,
    decision_id: decision.id,
    agent: item.agent,
    original_vote: item.vote,
    vote: item.vote,
    confidence: item.confidence,
    rebuttal: `${item.agent} maintains the vote after hearing peers.`,
    evidence_that_would_change: "Better evidence.",
    created_at: "2026-07-07T00:00:00Z",
  })),
  verdict: {
    id: "verdict-1",
    decision_id: decision.id,
    vote: "YES" as const,
    confidence: 0.74,
    summary: "Proceed, with a firm spending cap.",
    deciding_factor: "daily health benefit",
    minority_report: "Wallet remains concerned about the price.",
    created_at: "2026-07-07T00:00:00Z",
  },
};

afterEach(() => vi.restoreAllMocks());

describe("The Committee experience", () => {
  it("opens with a distinct decision intake and committee roster", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /some decisions deserve/i })).toBeInTheDocument();
    expect(screen.getAllByText("Wallet")).toHaveLength(2);
    expect(screen.getAllByText("Future Me")).toHaveLength(2);
    expect(screen.getAllByText("Chaos")).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: /skeptic/i })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /heart/i })).toBeDisabled();
  });

  it("lets the user replace a voting member with an alternative perspective", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const payload = JSON.parse(String(init?.body)) as { agent_roster: string[] };
      return new Response(JSON.stringify({ ...decision, agent_roster: payload.agent_roster }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("checkbox", { name: /chaos/i }));
    await user.click(screen.getByRole("checkbox", { name: /skeptic/i }));
    await user.type(screen.getByLabelText(/question before/i), decision.question);
    await user.click(screen.getByRole("button", { name: /enter it on the docket/i }));

    expect(await screen.findByText("Voting members")).toBeInTheDocument();
    expect(screen.getByText("Skeptic")).toBeInTheDocument();
    const submitted = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body)) as {
      agent_roster: string[];
    };
    expect(submitted.agent_roster).toEqual(["wallet", "future_me", "skeptic"]);
  });

  it("moves through context review, debate, verdict, and minority report", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const payload = init?.method === "POST" && init.body ? JSON.parse(String(init.body)) : null;
      const body = payload?.question ? decision : detail;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText(/question before/i), decision.question);
    await user.type(screen.getByLabelText(/what should they know/i), decision.context);
    await user.click(screen.getByRole("button", { name: /enter it on the docket/i }));

    expect(await screen.findByRole("heading", { name: /before the doors close/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /call the room to order/i }));

    expect(await screen.findByText("Ruling of the Chair")).toBeInTheDocument();
    expect(screen.getByText(/wallet remains concerned/i)).toBeInTheDocument();
    expect(screen.getAllByText("After hearing the room")).toHaveLength(3);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
