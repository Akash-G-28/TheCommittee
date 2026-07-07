import type { AgentName, Decision, DecisionDetail, PerformanceReport, Vote } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function createDecision(input: {
  question: string;
  category: string;
  context: string;
  agent_roster: AgentName[];
}): Promise<Decision> {
  return request<Decision>("/decisions", { method: "POST", body: JSON.stringify(input) });
}

export function deliberate(decisionId: string): Promise<DecisionDetail> {
  return request<DecisionDetail>(`/decisions/${decisionId}/deliberate`, { method: "POST" });
}

export function getPerformance(): Promise<PerformanceReport> {
  return request<PerformanceReport>("/committee/performance");
}

export function recordOutcome(
  decisionId: string,
  input: {
    actual_action: string;
    actual_choice: Vote;
    satisfaction_score: number;
    regret_score: number;
    reflection: string;
  },
): Promise<unknown> {
  return request(`/decisions/${decisionId}/outcome`, {
    method: "POST",
    body: JSON.stringify({ ...input, status: "RESOLVED" }),
  });
}
