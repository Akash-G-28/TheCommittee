import { useEffect, useMemo, useState, type FormEvent } from "react";
import { createDecision, deliberate, getPerformance, recordOutcome } from "./api";
import type {
  AgentName,
  Decision,
  DecisionDetail,
  Opinion,
  PerformanceReport,
  RevisedOpinion,
  Vote,
} from "./types";

type View = "convene" | "history" | "performance" | "follow-up";

const agentMeta: Record<
  AgentName,
  { name: string; title: string; sigil: string; motto: string }
> = {
  wallet: {
    name: "Wallet",
    title: "Keeper of Means",
    sigil: "₹",
    motto: "Every yes spends another possibility.",
  },
  future_me: {
    name: "Future Me",
    title: "Delegate from Tomorrow",
    sigil: "⌛",
    motto: "Choose the story you want to inherit.",
  },
  chaos: {
    name: "Chaos",
    title: "Minister of Elsewhere",
    sigil: "✦",
    motto: "A reversible leap still counts as living.",
  },
  skeptic: {
    name: "Skeptic",
    title: "Examiner of Claims",
    sigil: "?",
    motto: "Confidence is not evidence.",
  },
  heart: {
    name: "Heart",
    title: "Keeper of What Matters",
    sigil: "H",
    motto: "A practical answer can still be the wrong life.",
  },
};

const allAgents = Object.keys(agentMeta) as AgentName[];
const defaultRoster: AgentName[] = ["wallet", "future_me", "chaos"];

const categories = ["purchase", "travel", "career", "fitness", "creative", "general"];

export default function App() {
  const [view, setView] = useState<View>("convene");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [history, setHistory] = useState<DecisionDetail[]>([]);
  const [performance, setPerformance] = useState<PerformanceReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (view !== "performance" || performance) return;
    void getPerformance().then(setPerformance).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "The ledger could not be opened.");
    });
  }, [view, performance]);

  async function begin(input: {
    question: string;
    category: string;
    context: string;
    agent_roster: AgentName[];
  }) {
    setBusy(true);
    setError(null);
    try {
      setDecision(await createDecision(input));
      setDetail(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The clerk could not file the question.");
    } finally {
      setBusy(false);
    }
  }

  async function convene() {
    if (!decision) return;
    setBusy(true);
    setError(null);
    try {
      const result = await deliberate(decision.id);
      setDetail(result);
      setHistory((items) => [result, ...items.filter((item) => item.decision.id !== decision.id)]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Deliberation was interrupted.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setDecision(null);
    setDetail(null);
    setError(null);
    setView("convene");
  }

  return (
    <div className="app-shell">
      <Header view={view} setView={setView} reset={reset} />
      <main>
        {error && (
          <div className="error-banner" role="alert">
            <span>Proceedings paused.</span> {error}
          </div>
        )}

        {view === "convene" && !decision && <DecisionIntake onSubmit={begin} busy={busy} />}
        {view === "convene" && decision && !detail && (
          <ContextReview decision={decision} onConvene={convene} busy={busy} onBack={reset} />
        )}
        {view === "convene" && detail && (
          <DeliberationRoom detail={detail} onFollowUp={() => setView("follow-up")} />
        )}
        {view === "history" && <DecisionHistory items={history} onOpen={openHistoryItem} />}
        {view === "performance" && <CommitteePerformance report={performance} />}
        {view === "follow-up" && (
          <OutcomeFollowUp detail={detail} onSaved={() => setView("performance")} />
        )}
      </main>
      <footer>
        <span>The Committee</span>
        <span>Advice with arguments attached.</span>
      </footer>
    </div>
  );

  function openHistoryItem(item: DecisionDetail) {
    setDecision(item.decision);
    setDetail(item);
    setView("convene");
  }
}

function Header({
  view,
  setView,
  reset,
}: {
  view: View;
  setView: (view: View) => void;
  reset: () => void;
}) {
  return (
    <header className="site-header">
      <button className="wordmark" onClick={reset} aria-label="Return to decision intake">
        <span className="seal">C</span>
        <span>
          <strong>The Committee</strong>
          <small>Private deliberation chamber</small>
        </span>
      </button>
      <nav aria-label="Primary navigation">
        {([
          ["convene", "Convene"],
          ["history", "The archive"],
          ["performance", "The ledger"],
        ] as const).map(([target, label]) => (
          <button
            key={target}
            className={view === target ? "active" : ""}
            onClick={() => setView(target)}
          >
            {label}
          </button>
        ))}
      </nav>
    </header>
  );
}

function DecisionIntake({
  onSubmit,
  busy,
}: {
  onSubmit: (input: {
    question: string;
    category: string;
    context: string;
    agent_roster: AgentName[];
  }) => Promise<void>;
  busy: boolean;
}) {
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState("general");
  const [context, setContext] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<AgentName[]>(defaultRoster);

  function submit(event: FormEvent) {
    event.preventDefault();
    void onSubmit({ question, category, context, agent_roster: selectedAgents });
  }

  function toggleAgent(agent: AgentName) {
    setSelectedAgents((current) => {
      if (current.includes(agent)) return current.filter((item) => item !== agent);
      if (current.length === 3) return current;
      return [...current, agent];
    });
  }

  return (
    <section className="intake-layout">
      <div className="intake-copy">
        <p className="eyebrow">Docket now open</p>
        <h1>Some decisions deserve a room of their own.</h1>
        <p className="lede">
          Bring one choice, choose three perspectives, and let the Chairperson make them show
          their work. The Chair guides the ruling but does not cast a peer vote.
        </p>
        <div className="member-roll" aria-label="Committee members">
          {selectedAgents.map((agent) => (
            <div key={agent} className={`mini-member ${agent}`}>
              <span>{agentMeta[agent].sigil}</span>
              <div>
                <strong>{agentMeta[agent].name}</strong>
                <small>{agentMeta[agent].title}</small>
              </div>
            </div>
          ))}
        </div>
      </div>

      <form className="docket-card" onSubmit={submit}>
        <div className="docket-heading">
          <span>Form 01</span>
          <span>For considered matters</span>
        </div>
        <label htmlFor="question">The question before the room</label>
        <textarea
          id="question"
          value={question}
          minLength={3}
          required
          placeholder="Should I spend ₹28,000 on an ergonomic chair?"
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="field-row">
          <div>
            <label htmlFor="category">Docket</label>
            <select
              id="category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item[0]?.toUpperCase()}{item.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div className="privacy-note">
            <span>Private record</span>
            <small>Context stays in your local committee archive.</small>
          </div>
        </div>
        <label htmlFor="context">
          What should they know? <span>optional</span>
        </label>
        <textarea
          id="context"
          className="compact"
          value={context}
          placeholder="Budget, timing, constraints, what keeps tugging at you…"
          onChange={(event) => setContext(event.target.value)}
        />
        <fieldset className="roster-picker">
          <legend>
            Choose three voting members <span>{selectedAgents.length}/3 seated</span>
          </legend>
          <p>The original trio is preselected. Deselect one to invite an alternative voice.</p>
          <div className="roster-options">
            {allAgents.map((agent) => {
              const selected = selectedAgents.includes(agent);
              const full = selectedAgents.length === 3;
              return (
                <label key={agent} className={`${agent} ${selected ? "selected" : ""}`}>
                  <input
                    type="checkbox"
                    checked={selected}
                    disabled={!selected && full}
                    onChange={() => toggleAgent(agent)}
                  />
                  <span className="roster-sigil">{agentMeta[agent].sigil}</span>
                  <span>
                    <strong>{agentMeta[agent].name}</strong>
                    <small>{agentMeta[agent].title}</small>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
        <button
          className="primary-action"
          disabled={busy || question.trim().length < 3 || selectedAgents.length !== 3}
        >
          {busy ? "Filing the question…" : "Enter it on the docket"}
          <span aria-hidden="true">→</span>
        </button>
      </form>
    </section>
  );
}

function ContextReview({
  decision,
  onConvene,
  onBack,
  busy,
}: {
  decision: Decision;
  onConvene: () => Promise<void>;
  onBack: () => void;
  busy: boolean;
}) {
  return (
    <section className="review-page page-narrow">
      <p className="eyebrow">Context review · Docket {decision.id.slice(0, 8)}</p>
      <h1>Before the doors close.</h1>
      <p className="lede">This is the record each member receives before forming an independent view.</p>
      <article className="record-sheet">
        <span className="record-label">Question</span>
        <h2>{decision.question}</h2>
        <div className="record-meta">
          <span>{decision.category}</span>
          <span>Submitted {new Date(decision.created_at).toLocaleDateString()}</span>
        </div>
        <hr />
        <span className="record-label">Supporting context</span>
        <p>{decision.context || "No additional context was entered."}</p>
        <hr />
        <span className="record-label">Voting members</span>
        <div className="review-roster">
          {decision.agent_roster.map((agent) => (
            <span key={agent}>{agentMeta[agent].name}</span>
          ))}
          <small>Chairperson synthesizes without a peer vote.</small>
        </div>
      </article>
      <div className="review-actions">
        <button className="text-action" onClick={onBack}>Revise the filing</button>
        <button className="primary-action" onClick={() => void onConvene()} disabled={busy}>
          {busy ? "The committee is deliberating…" : "Call the room to order"}
          <span>↗</span>
        </button>
      </div>
    </section>
  );
}

function DeliberationRoom({
  detail,
  onFollowUp,
}: {
  detail: DecisionDetail;
  onFollowUp: () => void;
}) {
  const revisions = useMemo(
    () => new Map(detail.revised_opinions.map((item) => [item.agent, item])),
    [detail.revised_opinions],
  );
  return (
    <section className="room-page">
      <div className="room-heading">
        <div>
          <p className="eyebrow">Proceedings concluded · {detail.decision.category}</p>
          <h1>{detail.decision.question}</h1>
        </div>
        <div className="round-stamp">
          <strong>{detail.rounds.length}/2</strong>
          <span>rounds sealed</span>
        </div>
      </div>

      <div className="process-line" aria-label="Deliberation progress">
        <span className="done">Independent opinions</span>
        <span className="done">Cross-examination</span>
        <span className="done">Chairperson's ruling</span>
      </div>

      <div className="agent-grid">
        {detail.opinions.map((opinion) => (
          <AgentCard key={opinion.id} opinion={opinion} revision={revisions.get(opinion.agent)} />
        ))}
      </div>

      {detail.verdict && <VerdictCard detail={detail} />}

      <div className="aftercare">
        <div>
          <p className="eyebrow">The decision is still yours</p>
          <h2>Return when real life has voted.</h2>
          <p>Record what you chose and whether the committee earned your trust.</p>
        </div>
        <button className="secondary-action" onClick={onFollowUp}>Schedule the reckoning →</button>
      </div>
    </section>
  );
}

function AgentCard({ opinion, revision }: { opinion: Opinion; revision?: RevisedOpinion }) {
  const meta = agentMeta[opinion.agent];
  const changed = revision && revision.vote !== revision.original_vote;
  return (
    <article className={`agent-card ${opinion.agent}`}>
      <div className="agent-identity">
        <span className="agent-sigil">{meta.sigil}</span>
        <div><h2>{meta.name}</h2><small>{meta.title}</small></div>
      </div>
      <div className="vote-line">
        <VoteBadge vote={revision?.vote ?? opinion.vote} />
        <span>{Math.round((revision?.confidence ?? opinion.confidence) * 100)}% conviction</span>
      </div>
      <p className="opinion-summary">{opinion.summary}</p>
      <ul>{opinion.key_factors.map((factor) => <li key={factor}>{factor}</li>)}</ul>
      {revision && (
        <div className="rebuttal">
          <span className="rebuttal-label">After hearing the room</span>
          {changed && <strong className="vote-change">Vote changed {revision.original_vote} → {revision.vote}</strong>}
          <p>{revision.rebuttal}</p>
          <details><summary>What could change this?</summary><p>{revision.evidence_that_would_change}</p></details>
        </div>
      )}
      <blockquote>“{meta.motto}”</blockquote>
    </article>
  );
}

function VoteBadge({ vote }: { vote: Vote }) {
  return <strong className={`vote-badge vote-${vote.toLowerCase()}`}>{vote}</strong>;
}

function VerdictCard({ detail }: { detail: DecisionDetail }) {
  const verdict = detail.verdict!;
  const votes = detail.revised_opinions.map((item) => item.vote);
  return (
    <article className="verdict-card">
      <div className="chair-seal">C</div>
      <div className="verdict-main">
        <p className="eyebrow">Ruling of the Chair</p>
        <div className="verdict-title"><VoteBadge vote={verdict.vote} /><h2>{verdict.summary}</h2></div>
        <div className="confidence-rule">
          <span style={{ width: `${verdict.confidence * 100}%` }} />
        </div>
        <div className="verdict-stats">
          <div><small>Confidence</small><strong>{Math.round(verdict.confidence * 100)}%</strong></div>
          <div><small>Vote breakdown</small><strong>{votes.join(" · ")}</strong></div>
          <div><small>Deciding factor</small><strong>{verdict.deciding_factor}</strong></div>
        </div>
      </div>
      <aside className="minority-report">
        <span>Minority report</span>
        <p>{verdict.minority_report || "The room reached a unanimous position."}</p>
      </aside>
    </article>
  );
}

function DecisionHistory({
  items,
  onOpen,
}: {
  items: DecisionDetail[];
  onOpen: (item: DecisionDetail) => void;
}) {
  return (
    <section className="page-narrow archive-page">
      <p className="eyebrow">The archive</p><h1>Past proceedings.</h1>
      <p className="lede">Every verdict keeps its arguments, dissent, and eventual outcome attached.</p>
      {items.length === 0 ? (
        <div className="empty-state"><span>∅</span><h2>The shelves are quiet.</h2><p>Convene your first decision to begin the archive.</p></div>
      ) : (
        <div className="archive-list">{items.map((item) => (
          <button key={item.decision.id} onClick={() => onOpen(item)}>
            <span className="archive-category">{item.decision.category}</span>
            <strong>{item.decision.question}</strong>
            <span><VoteBadge vote={item.verdict?.vote ?? "MAYBE"} /> {new Date(item.decision.created_at).toLocaleDateString()}</span>
          </button>
        ))}</div>
      )}
    </section>
  );
}

function CommitteePerformance({ report }: { report: PerformanceReport | null }) {
  return (
    <section className="page-narrow ledger-page">
      <p className="eyebrow">The ledger</p><h1>Are they any good?</h1>
      <p className="lede">Accuracy is earned only after real outcomes arrive. Small samples stay visible.</p>
      {!report ? <div className="loading-mark">Opening the ledger…</div> : (
        <>
          <div className="ledger-summary"><strong>{report.resolved_decisions}</strong><span>resolved decisions scored</span></div>
          <div className="performance-grid">
            {allAgents.map((agent) => {
              const rows = report.agent_performance.filter((item) => item.agent === agent);
              const average = rows.length ? rows.reduce((sum, row) => sum + row.accuracy, 0) / rows.length : null;
              return <article key={agent} className={`performance-card ${agent}`}>
                <span className="agent-sigil">{agentMeta[agent].sigil}</span><h2>{agentMeta[agent].name}</h2>
                <strong>{average === null ? "—" : `${Math.round(average * 100)}%`}</strong><small>outcome-conditioned accuracy</small>
                {rows.map((row) => <div className="category-row" key={row.category}><span>{row.category}</span><span>{Math.round(row.accuracy * 100)}% · n={row.resolved_count}</span></div>)}
              </article>;
            })}
          </div>
          <details className="methodology"><summary>How the ledger scores advice</summary><p>{report.methodology}</p></details>
        </>
      )}
    </section>
  );
}

function OutcomeFollowUp({ detail, onSaved }: { detail: DecisionDetail | null; onSaved: () => void }) {
  const [choice, setChoice] = useState<Vote>("YES");
  const [satisfaction, setSatisfaction] = useState(7);
  const [regret, setRegret] = useState(2);
  const [reflection, setReflection] = useState("");
  const [saving, setSaving] = useState(false);
  if (!detail) return <section className="page-narrow empty-state"><h1>No decision selected.</h1><p>Open a verdict from the archive first.</p></section>;

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true);
    try {
      await recordOutcome(detail!.decision.id, { actual_action: choice === "YES" ? "Took the action" : choice === "NO" ? "Did not take the action" : "Deferred", actual_choice: choice, satisfaction_score: satisfaction, regret_score: regret, reflection });
      onSaved();
    } finally { setSaving(false); }
  }

  return <section className="page-narrow follow-up-page">
    <p className="eyebrow">Outcome follow-up</p><h1>Real life has the floor.</h1><p className="lede">{detail.decision.question}</p>
    <form className="outcome-form" onSubmit={(event) => void save(event)}>
      <fieldset><legend>What did you actually choose?</legend><div className="choice-row">{(["YES", "NO", "MAYBE"] as Vote[]).map((vote) => <label key={vote}><input type="radio" name="choice" checked={choice === vote} onChange={() => setChoice(vote)} />{vote === "YES" ? "I did it" : vote === "NO" ? "I didn't" : "I deferred"}</label>)}</div></fieldset>
      <RangeField label="Satisfaction" value={satisfaction} setValue={setSatisfaction} low="Not at all" high="Deeply" />
      <RangeField label="Regret" value={regret} setValue={setRegret} low="None" high="A great deal" />
      <label htmlFor="reflection">What happened?</label><textarea id="reflection" required minLength={1} value={reflection} onChange={(event) => setReflection(event.target.value)} placeholder="What surprised you? What would you tell the committee now?" />
      <button className="primary-action" disabled={saving}>{saving ? "Entering the outcome…" : "Enter outcome into the record"}<span>→</span></button>
    </form>
  </section>;
}

function RangeField({ label, value, setValue, low, high }: { label: string; value: number; setValue: (value: number) => void; low: string; high: string }) {
  return <label className="range-field">{label}<strong>{value}/10</strong><input type="range" min="0" max="10" value={value} onChange={(event) => setValue(Number(event.target.value))} /><span><small>{low}</small><small>{high}</small></span></label>;
}
