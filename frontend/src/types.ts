export type Vote = "YES" | "NO" | "MAYBE";
export type AgentName = "wallet" | "future_me" | "chaos" | "skeptic" | "heart";

export interface Decision {
  id: string;
  question: string;
  category: string;
  context: string | null;
  agent_roster: AgentName[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Opinion {
  id: string;
  decision_id: string;
  agent: AgentName;
  vote: Vote;
  confidence: number;
  summary: string;
  key_factors: string[];
  created_at: string;
}

export interface RevisedOpinion {
  id: string;
  decision_id: string;
  agent: AgentName;
  original_vote: Vote;
  vote: Vote;
  confidence: number;
  rebuttal: string;
  evidence_that_would_change: string;
  created_at: string;
}

export interface Verdict {
  id: string;
  decision_id: string;
  vote: Vote;
  confidence: number;
  summary: string;
  deciding_factor: string;
  minority_report: string | null;
  created_at: string;
}

export interface DecisionDetail {
  decision: Decision;
  opinions: Opinion[];
  rounds: Array<{ round_number: number; status: string }>;
  revised_opinions: RevisedOpinion[];
  verdict: Verdict | null;
}

export interface PerformanceReport {
  resolved_decisions: number;
  agent_performance: Array<{
    category: string;
    agent: AgentName;
    resolved_count: number;
    accuracy: number;
  }>;
  calibration: Array<{
    lower_bound: number;
    upper_bound: number;
    sample_count: number;
    mean_confidence: number;
    mean_score: number;
    calibration_gap: number;
  }>;
  methodology: string;
}
