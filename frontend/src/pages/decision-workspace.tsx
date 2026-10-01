import { useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  Circle,
  Clock3,
  FileText,
  GitBranch,
  History,
  PencilLine,
  Quote,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SourcePreview } from "@/components/source-preview";
import { history, initialRationale, sources, type Source } from "@/data/sample";

type Section = "Overview" | "History";
export function DecisionWorkspace() {
  const [section, setSection] = useState<Section>("Overview");
  const [source, setSource] = useState<Source | null>(null);
  const [selected, setSelected] = useState("B");
  const [rationale, setRationale] = useState(initialRationale);
  const [draftRationale, setDraftRationale] = useState(initialRationale);
  const [editing, setEditing] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [finalized, setFinalized] = useState(false);
  const [notice, setNotice] = useState("");
  const selectedTitle =
    selected === "B" ? "Reduce the operating limit" : "Keep the current limit";
  return (
    <div className="decision-page page-enter">
      <div className="page-heading-row">
        <div className="eyebrow">
          DECISION RECORD <span className="eyebrow-separator" /> DEC-024
        </div>
        <span className={`status-badge ${finalized ? "ready" : "review"}`}>
          <span />
          {finalized ? "Decided · preview" : "In review"}
        </span>
      </div>
      <div className="decision-intro">
        <div>
          <h1>
            Every decision.
            <br />
            <em>A clear reason.</em>
          </h1>
          <p className="intro-description">
            Review the alternatives. Follow the evidence.
            <br className="desktop-break" /> Make the reasoning part of the
            record.
          </p>
        </div>
        <div className="intro-annotation">
          <span>ENGINEERING REVIEW</span>
          <div className="annotation-line" />
          <span>01 / ACTIVE DECISION</span>
        </div>
      </div>
      <section
        className="decision-title-block"
        aria-labelledby="decision-question"
      >
        <div>
          <div className="eyebrow">THE QUESTION</div>
          <h2 id="decision-question">
            Should we reduce the cooling-system
            <br className="wide-break" /> operating pressure?
          </h2>
          <div className="record-meta">
            <span className="mini-avatar">AR</span>
            <span>Avery Reed</span>
            <span className="meta-dot">·</span>
            <span>Created 29 Sep 2026</span>
            <span className="meta-dot">·</span>
            <span>Cooling systems</span>
          </div>
        </div>
        <Button
          className="primary-action"
          onClick={() => setReviewing(true)}
          disabled={finalized}
        >
          {finalized ? <Check size={16} /> : <CheckCircle2 size={16} />}
          {finalized ? "Preview finalized" : "Review decision"}
          {!finalized && <ArrowRight size={16} />}
        </Button>
      </section>
      <div className="section-tabs" role="group" aria-label="Decision sections">
        {(["Overview", "History"] as Section[]).map((tab) => (
          <button
            key={tab}
            aria-pressed={section === tab}
            className={section === tab ? "active" : ""}
            onClick={() => setSection(tab)}
          >
            {tab === "History" && <History size={15} />}
            {tab}
            {tab === "History" && <span>{finalized ? "6" : "5"}</span>}
          </button>
        ))}
        <span className="tabs-note">
          <span /> Sample record
        </span>
      </div>
      {section === "Overview" ? (
        <div className="decision-grid">
          <div className="decision-main">
            <div className="section-heading">
              <div>
                <span className="section-number">01</span>
                <h3>The alternatives</h3>
              </div>
              <span className="muted small">Two paths forward</span>
            </div>
            <fieldset className="alternatives" disabled={finalized}>
              <legend className="sr-only">Preferred alternative</legend>
              {[
                {
                  id: "A",
                  title: "Keep the current limit",
                  description:
                    "Maintain the approved 6 bar operating limit and monitor pressure during pump changeover.",
                  detail: "No operating change",
                  count: "No linked evidence",
                },
                {
                  id: "B",
                  title: "Reduce the operating limit",
                  description:
                    "Lower the nominal set point to increase the safety margin during transient conditions.",
                  detail: "Greater pressure headroom",
                  count: "2 supporting sources",
                },
              ].map((alternative) => (
                <label
                  key={alternative.id}
                  className={`alternative ${selected === alternative.id ? "selected" : ""}`}
                >
                  <input
                    type="radio"
                    name="alternative"
                    value={alternative.id}
                    checked={selected === alternative.id}
                    onChange={() => setSelected(alternative.id)}
                  />
                  <div className="alternative-top">
                    <span className="alternative-letter">{alternative.id}</span>
                    <span className="choice-indicator">
                      {selected === alternative.id ? (
                        <CheckCircle2 size={18} />
                      ) : (
                        <Circle size={18} />
                      )}
                    </span>
                  </div>
                  <h4>{alternative.title}</h4>
                  <p>{alternative.description}</p>
                  <div className="alternative-benefit">
                    <GitBranch size={14} />
                    {alternative.detail}
                  </div>
                  <div className="alternative-bottom">
                    <FileText size={13} />
                    {alternative.count}
                  </div>
                </label>
              ))}
            </fieldset>
            <section className="rationale-section">
              <div className="section-heading">
                <div>
                  <span className="section-number">02</span>
                  <h3>The rationale</h3>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={finalized}
                  onClick={() => {
                    setDraftRationale(rationale);
                    setEditing(true);
                  }}
                >
                  <PencilLine size={14} /> Edit rationale
                </Button>
              </div>
              <div className="rationale-copy">
                <Quote size={24} strokeWidth={1.2} />
                <p>{rationale}</p>
              </div>
              <div className="rationale-byline">
                <span className="mini-avatar">AR</span>
                <span>Reasoning by Avery Reed</span>
                <span className="muted">· Example draft</span>
              </div>
            </section>
            <div className="trace-note">
              <GitBranch size={18} />
              <p>
                <strong>Reasoning you can retrace.</strong>
                <br />
                The selected alternative, cited evidence, and author stay
                together in the decision record.
              </p>
            </div>
          </div>
          <aside className="evidence-panel" aria-label="Supporting evidence">
            <div className="evidence-heading">
              <div>
                <span className="section-number">03</span>
                <h3>The evidence</h3>
              </div>
              <span className="evidence-count">02</span>
            </div>
            <p className="evidence-subtitle">Supporting alternative B</p>
            {sources.slice(0, 2).map((item, index) => (
              <article className="evidence-item" key={item.id}>
                <div className="evidence-topline">
                  <span className="source-index">
                    [{String(index + 1).padStart(2, "0")}]
                  </span>
                  <span className="supporting">
                    <span /> Supporting
                  </span>
                </div>
                <blockquote>“{item.excerpt}”</blockquote>
                <button
                  className="citation-link"
                  onClick={() => setSource(item)}
                >
                  <FileText size={15} />
                  <span>
                    {item.title}
                    <small>
                      {item.reference} · {item.version} · p. {item.page}
                    </small>
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              </article>
            ))}
            <div className="evidence-footer">
              <CheckCircle2 size={15} />
              <span>Every excerpt has a source.</span>
            </div>
          </aside>
        </div>
      ) : (
        <section className="history-section">
          <div className="section-heading">
            <div>
              <span className="section-number">01</span>
              <h3>A traceable history</h3>
            </div>
            <span className="muted small">Most recent first</span>
          </div>
          <ol className="timeline">
            {[
              ...(finalized
                ? [
                    {
                      title: "Decision finalized in preview",
                      detail: selectedTitle,
                      time: "Just now",
                      actor: "Avery Reed",
                    },
                  ]
                : []),
              ...history,
            ].map((event, index) => (
              <li key={event.title + index}>
                <span className="timeline-marker">
                  <Clock3 size={14} />
                </span>
                <div>
                  <h4>{event.title}</h4>
                  <p>{event.detail}</p>
                  <small>
                    {event.actor} <span>·</span> {event.time}
                  </small>
                </div>
              </li>
            ))}
          </ol>
          <p className="muted small">
            Illustrative activity. Live audit events will come from the backend.
          </p>
        </section>
      )}
      <p className="sr-only" role="status">
        {notice}
      </p>
      <SourcePreview source={source} onClose={() => setSource(null)} />
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit the example rationale</DialogTitle>
            <DialogDescription>
              Explain why this alternative is appropriate. Changes are only kept
              in this preview.
            </DialogDescription>
          </DialogHeader>
          <label className="field-label" htmlFor="rationale">
            Decision rationale
          </label>
          <textarea
            id="rationale"
            value={draftRationale}
            onChange={(event) => setDraftRationale(event.target.value)}
            rows={6}
            maxLength={4000}
          />
          <div className="dialog-actions">
            <Button variant="outline" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              disabled={draftRationale.trim().length < 10}
              onClick={() => {
                setRationale(draftRationale.trim());
                setEditing(false);
                setNotice("Example rationale updated.");
              }}
            >
              Update preview
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={reviewing} onOpenChange={setReviewing}>
        <DialogContent>
          <DialogHeader>
            <div className="eyebrow">DEC-024 / REVIEW</div>
            <DialogTitle>Make the reasoning explicit.</DialogTitle>
            <DialogDescription>
              Review your selection in this example record. Nothing will be
              saved to the backend.
            </DialogDescription>
          </DialogHeader>
          <div className="review-selection">
            <span className="alternative-letter">{selected}</span>
            <div>
              <small>SELECTED ALTERNATIVE</small>
              <h3>{selectedTitle}</h3>
            </div>
          </div>
          <p className="dialog-copy">{rationale}</p>
          {selected === "A" && (
            <p className="review-warning">
              The linked evidence supports alternative B. Review whether your
              rationale explains the choice of alternative A.
            </p>
          )}
          <div className="dialog-actions">
            <Button variant="outline" onClick={() => setReviewing(false)}>
              Keep reviewing
            </Button>
            <Button
              onClick={() => {
                setFinalized(true);
                setReviewing(false);
                setNotice(
                  "Example decision finalized in preview. Refresh to reset.",
                );
              }}
            >
              Finalize preview <Check size={15} />
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
