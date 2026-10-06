import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { ArrowLeft, ArrowRight, FileText, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DecisionAlternatives } from "@/components/decision-alternatives";
import { ApiFeedback } from "@/components/api-feedback";
import { useAuthAction } from "@/auth/use-auth-action";
import { apiRequest, type ApiError } from "@/lib/api";
import {
  formatDate,
  isUuid,
  parseDecision,
  parseDecisionList,
  parseDecisionRecord,
  statusLabels,
  type DecisionStatus,
} from "@/lib/decisions";
import { useApiResource } from "@/lib/use-api-resource";

function Status({ status }: { status: DecisionStatus }) {
  return (
    <span className={`live-status live-status-${status}`}>
      {statusLabels[status]}
    </span>
  );
}
function LoadFailure({ error, retry }: { error: ApiError; retry: () => void }) {
  return (
    <div className="decision-load-error">
      <ApiFeedback error={error} />
      <Button variant="outline" onClick={retry}>
        Try again
      </Button>
    </div>
  );
}
export function DecisionListPage() {
  const [search, setSearch] = useSearchParams();
  const requested = Number(search.get("offset") ?? 0);
  const offset =
    Number.isSafeInteger(requested) && requested >= 0 && requested <= 1000000
      ? requested
      : 0;
  const { resource, retry } = useApiResource(
    `/decisions?offset=${offset}&limit=20`,
    parseDecisionList,
  );
  return (
    <>
      <div className="eyebrow">YOUR DECISION REGISTER</div>
      <div className="decision-heading">
        <div>
          <h1>Decisions.</h1>
          <p className="intro-description">
            A question, its evidence, and a record you can return to.
          </p>
        </div>
        <Button asChild>
          <Link to="/workspace/decisions/new">
            <Plus size={16} />
            New decision
          </Link>
        </Button>
      </div>
      {resource.status === "loading" && (
        <p className="decision-state" role="status">
          Loading your decisions…
        </p>
      )}
      {resource.status === "error" && (
        <LoadFailure error={resource.error} retry={retry} />
      )}
      {resource.status === "ready" && (
        <>
          <p className="decision-count" role="status">
            {resource.data.total}{" "}
            {resource.data.total === 1 ? "decision" : "decisions"} in your
            register
          </p>
          {resource.data.items.length === 0 ? (
            <section className="decision-empty">
              <FileText size={30} aria-hidden="true" />
              <h2>
                {offset === 0
                  ? "Every decision starts with a question."
                  : "No decisions on this page."}
              </h2>
              <p>
                {offset === 0
                  ? "Capture what needs to be decided. Your draft will be saved to your account."
                  : "Your register may have changed. Return to the first page."}
              </p>
              {offset === 0 ? (
                <Button asChild>
                  <Link to="/workspace/decisions/new">
                    Create your first decision <ArrowRight size={16} />
                  </Link>
                </Button>
              ) : (
                <Button onClick={() => setSearch({ offset: "0" })}>
                  Return to first page
                </Button>
              )}
            </section>
          ) : (
            <ol className="decision-register">
              {resource.data.items.map((decision, index) => (
                <li key={decision.id}>
                  <Link to={`/workspace/decisions/${decision.id}`}>
                    <span className="register-number" aria-hidden="true">
                      {String(offset + index + 1).padStart(2, "0")}
                    </span>
                    <div className="register-copy">
                      <div className="register-title">
                        <h2>{decision.title}</h2>
                        <Status status={decision.status} />
                      </div>
                      <p>{decision.question}</p>
                      <span className="register-date">
                        Updated{" "}
                        <time dateTime={decision.updated_at}>
                          {formatDate(decision.updated_at)}
                        </time>
                      </span>
                    </div>
                    <ArrowRight
                      className="register-arrow"
                      size={20}
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ol>
          )}
          {(offset > 0 || resource.data.total > 20) && (
            <nav className="decision-pagination" aria-label="Decision pages">
              <Button
                variant="outline"
                disabled={offset === 0}
                onClick={() =>
                  setSearch({ offset: String(Math.max(0, offset - 20)) })
                }
              >
                Previous
              </Button>
              <span>Page {Math.floor(offset / 20) + 1}</span>
              <Button
                variant="outline"
                disabled={offset + 20 >= resource.data.total}
                onClick={() => setSearch({ offset: String(offset + 20) })}
              >
                Next
              </Button>
            </nav>
          )}
        </>
      )}
    </>
  );
}

export function CreateDecisionPage() {
  const navigate = useNavigate();
  const { busy, error, run } = useAuthAction();
  const [validation, setValidation] = useState<string | null>(null);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim(),
      question = String(form.get("question") ?? "").trim();
    if (title.length < 3 || question.length < 10) {
      setValidation(
        "Use at least 3 characters for the title and 10 for the question, excluding surrounding spaces.",
      );
      return;
    }
    setValidation(null);
    void run(async (signal) => {
      const decision = parseDecision(
        await apiRequest("/decisions", {
          method: "POST",
          body: { title, question },
          signal,
          expectedStatus: 201,
        }),
      );
      navigate(`/workspace/decisions/${decision.id}`, { replace: true });
    });
  }
  return (
    <>
      <Link className="decision-back" to="/workspace/decisions">
        <ArrowLeft size={15} />
        All decisions
      </Link>
      <div className="eyebrow">START A DECISION RECORD</div>
      <h1>Frame the question.</h1>
      <p className="intro-description">
        Give the decision a clear name and describe what needs to be resolved.
      </p>
      <form className="decision-create-form" onSubmit={submit} aria-busy={busy}>
        <label htmlFor="decision-title">Decision title</label>
        <p className="field-help" id="title-help">
          3–200 characters. Keep it specific and easy to find.
        </p>
        <input
          id="decision-title"
          name="title"
          required
          minLength={3}
          maxLength={200}
          aria-describedby="title-help"
          disabled={busy}
          autoFocus
        />
        <label htmlFor="decision-question">Question to resolve</label>
        <p className="field-help" id="question-help">
          10–2,000 characters. What choice needs to be made, and why?
        </p>
        <textarea
          id="decision-question"
          name="question"
          required
          minLength={10}
          maxLength={2000}
          aria-describedby="question-help"
          rows={6}
          disabled={busy}
        />
        {validation && (
          <p className="api-feedback" role="alert">
            {validation}
          </p>
        )}
        {error && <ApiFeedback error={error} />}
        {error && (error.status === 0 || error.status >= 500) && (
          <p className="field-help">
            If the connection failed after saving, the draft may already exist.{" "}
            <Link className="text-action" to="/workspace/decisions">
              Check your decisions
            </Link>{" "}
            before trying again.
          </p>
        )}
        <div className="decision-form-actions">
          <Button type="submit" disabled={busy}>
            {busy ? "Saving decision…" : "Save decision"}
            <ArrowRight size={16} />
          </Button>
          <Link to="/workspace/decisions">Cancel</Link>
        </div>
        <p className="field-help">
          This creates a draft. Creating a decision does not upload documents or
          generate embeddings.
        </p>
      </form>
    </>
  );
}

export function DecisionRecordPage() {
  const { decisionId } = useParams();
  const [notice, setNotice] = useState<{ id: string; message: string } | null>(
    null,
  );
  const valid = isUuid(decisionId);
  const { resource, retry } = useApiResource(
    valid ? `/decisions/${decisionId}/record` : null,
    parseDecisionRecord,
  );
  const missing =
    !valid || (resource.status === "error" && resource.error.status === 404);
  return (
    <>
      <Link className="decision-back" to="/workspace/decisions">
        <ArrowLeft size={15} />
        All decisions
      </Link>
      {missing ? (
        <>
          <h1>Decision unavailable.</h1>
          <p className="intro-description">
            This decision could not be found in your account. Check the link or
            return to your decisions.
          </p>
        </>
      ) : resource.status === "loading" ? (
        <>
          <h1>Opening the record.</h1>
          <p role="status">Loading your saved decision…</p>
        </>
      ) : resource.status === "error" ? (
        <>
          <h1>Let’s reload the record.</h1>
          {notice?.id === decisionId && (
            <p role="status">
              {notice.message} Reload the record to see the latest version.
            </p>
          )}
          <LoadFailure error={resource.error} retry={retry} />
        </>
      ) : (
        <>
          <div className="decision-record-kicker">
            <span className="eyebrow">SAVED DECISION RECORD</span>
            <Status status={resource.data.status} />
          </div>
          <h1 className="live-record-title">{resource.data.title}</h1>
          <section
            className="live-record-question"
            aria-labelledby="question-heading"
          >
            <h2 id="question-heading">The question</h2>
            <p>{resource.data.question}</p>
          </section>
          <div className="record-columns">
            <div>
              <DecisionAlternatives
                key={resource.data.id}
                record={resource.data}
                notice={notice?.id === resource.data.id ? notice.message : null}
                onChanged={(message) => {
                  setNotice({ id: resource.data.id, message });
                  retry();
                }}
                onReload={() => {
                  setNotice(null);
                  retry();
                }}
              />
              <section
                className="live-record-section"
                aria-labelledby="outcome-heading"
              >
                <h2 id="outcome-heading">Recorded rationale</h2>
                <p
                  className={
                    resource.data.rationale
                      ? "record-prose"
                      : "record-empty-note"
                  }
                >
                  {resource.data.rationale ??
                    "No rationale has been recorded yet."}
                </p>
              </section>
              <p className="record-scope-note">
                Evidence linking and review actions will be available in a later
                update.
              </p>
            </div>
            <aside className="record-metadata" aria-label="Record details">
              <h2>Record details</h2>
              <dl>
                <div>
                  <dt>Created</dt>
                  <dd>
                    <time dateTime={resource.data.created_at}>
                      {formatDate(resource.data.created_at)}
                    </time>
                  </dd>
                </div>
                <div>
                  <dt>Last updated</dt>
                  <dd>
                    <time dateTime={resource.data.updated_at}>
                      {formatDate(resource.data.updated_at)}
                    </time>
                  </dd>
                </div>
                <div>
                  <dt>Created by · user ID</dt>
                  <dd>{resource.data.created_by_user_id ?? "Not recorded"}</dd>
                </div>
                <div>
                  <dt>Decided by · user ID</dt>
                  <dd>{resource.data.decided_by_user_id ?? "Not recorded"}</dd>
                </div>
                {(
                  [
                    ["Submitted", resource.data.submitted_at],
                    ["Decided", resource.data.decided_at],
                    ["Cancelled", resource.data.cancelled_at],
                    ["Superseded", resource.data.superseded_at],
                  ] as const
                ).map(
                  ([label, value]) =>
                    value && (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>
                          <time dateTime={value}>{formatDate(value)}</time>
                        </dd>
                      </div>
                    ),
                )}
                <div>
                  <dt>Audit events</dt>
                  <dd>{resource.data.history.total}</dd>
                </div>
                <div>
                  <dt>Record ID</dt>
                  <dd>{resource.data.id}</dd>
                </div>
              </dl>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
