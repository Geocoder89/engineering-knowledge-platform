import { useEffect, useRef, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiFeedback } from "@/components/api-feedback";
import { useAuthAction } from "@/auth/use-auth-action";
import { apiRequest } from "@/lib/api";
import { type Alternative, type DecisionRecord } from "@/lib/decisions";

type Action =
  { kind: "add" } | { kind: "edit" | "remove"; alternative: Alternative };
type EditorProps = {
  decisionId: string;
  action: Action;
  onCancel: () => void;
  onChanged: (message: string) => void;
  onReload: () => void;
};

function AlternativeEditor({
  decisionId,
  action,
  onCancel,
  onChanged,
  onReload,
}: EditorProps) {
  const alternative = action.kind === "add" ? null : action.alternative;
  const [title, setTitle] = useState(alternative?.title ?? "");
  const [description, setDescription] = useState(
    alternative?.description ?? "",
  );
  const [validation, setValidation] = useState<string | null>(null);
  const { busy, error, run } = useAuthAction();
  // A lost response may follow a committed write. Never automatically repeat it.
  const uncertain =
    !!error &&
    (error.status === 0 ||
      error.status >= 500 ||
      (error.status >= 200 && error.status < 300));
  const stale = error?.status === 409 || error?.status === 404;
  const needsReload = uncertain || stale;
  const unchanged =
    action.kind === "edit" &&
    title.trim() === alternative?.title &&
    description.trim() === alternative?.description;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || needsReload || unchanged) return;
    const values = { title: title.trim(), description: description.trim() };
    if (
      action.kind !== "remove" &&
      (values.title.length < 3 ||
        values.title.length > 200 ||
        values.description.length < 10 ||
        values.description.length > 4000)
    ) {
      setValidation(
        "Use 3–200 characters for the title and 10–4,000 for the description, excluding surrounding spaces.",
      );
      return;
    }
    setValidation(null);
    void run(async (signal) => {
      const changes =
        action.kind === "edit"
          ? {
              ...(values.title !== alternative?.title
                ? { title: values.title }
                : {}),
              ...(values.description !== alternative?.description
                ? { description: values.description }
                : {}),
            }
          : values;
      await apiRequest(
        `/decisions/${decisionId}/alternatives${alternative ? `/${alternative.id}` : ""}`,
        {
          method:
            action.kind === "add"
              ? "POST"
              : action.kind === "edit"
                ? "PATCH"
                : "DELETE",
          body: action.kind === "remove" ? undefined : changes,
          expectedStatus:
            action.kind === "add" ? 201 : action.kind === "edit" ? 200 : 204,
          // The canonical record is fetched after success, including evidence and audit count.
          responseType: "empty",
          signal,
        },
      );
      if (!signal.aborted)
        onChanged(
          action.kind === "add"
            ? "Alternative added."
            : action.kind === "edit"
              ? "Alternative updated."
              : "Alternative removed.",
        );
    });
  }

  return (
    <form
      className="decision-create-form alternative-editor"
      onSubmit={submit}
      aria-busy={busy}
      aria-labelledby="alternative-form-heading"
    >
      <h3 id="alternative-form-heading">
        {action.kind === "add"
          ? "Add an alternative"
          : action.kind === "edit"
            ? "Edit alternative"
            : "Remove this alternative?"}
      </h3>
      {action.kind === "remove" ? (
        <>
          <p>
            “{alternative?.title}” and its {alternative?.evidence.length ?? 0}{" "}
            linked evidence items will be removed from this decision. The source
            documents remain available. This cannot be undone.
          </p>
          <p className="field-help">
            The removal will remain in the decision’s audit history.
          </p>
        </>
      ) : (
        <>
          <label htmlFor="alternative-title">Alternative title</label>
          <p className="field-help" id="alternative-title-help">
            3–200 characters. Name the option you want to compare.
          </p>
          <input
            id="alternative-title"
            name="title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            minLength={3}
            maxLength={200}
            aria-describedby="alternative-title-help"
            disabled={busy}
            autoFocus
          />
          <label htmlFor="alternative-description">Description</label>
          <p className="field-help" id="alternative-description-help">
            10–4,000 characters. Explain what this option involves.
          </p>
          <textarea
            id="alternative-description"
            name="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            required
            minLength={10}
            maxLength={4000}
            aria-describedby="alternative-description-help"
            rows={5}
            disabled={busy}
          />
        </>
      )}
      {validation && (
        <p className="api-feedback" role="alert">
          {validation}
        </p>
      )}
      {error && (
        <ApiFeedback
          error={error}
          message={
            error.status === 409
              ? "This decision is no longer editable. Reload the record to see its current status."
              : error.status === 404
                ? "This decision or alternative is no longer available. Reload the record before continuing."
                : undefined
          }
        />
      )}
      {needsReload && (
        <div className="alternative-recovery">
          <p>
            {uncertain
              ? "We could not confirm the result. Your change may already have been saved. Check the saved record before trying again."
              : "Your entered text is still here so you can copy it before reloading."}{" "}
            Reloading clears this form.
          </p>
          <Button variant="outline" onClick={onReload}>
            Reload saved record
          </Button>
        </div>
      )}
      <div className="decision-form-actions">
        <Button
          type="submit"
          disabled={busy || needsReload || unchanged}
          className={
            action.kind === "remove" ? "alternative-remove" : undefined
          }
        >
          {busy
            ? "Saving change…"
            : action.kind === "add"
              ? "Save alternative"
              : action.kind === "edit"
                ? "Save changes"
                : "Confirm removal"}
        </Button>
        <Button
          variant="ghost"
          onClick={onCancel}
          disabled={busy || needsReload}
          autoFocus={action.kind === "remove"}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function DecisionAlternatives({
  record,
  notice,
  onChanged,
  onReload,
}: {
  record: DecisionRecord;
  notice: string | null;
  onChanged: (message: string) => void;
  onReload: () => void;
}) {
  const [action, setAction] = useState<Action | null>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => {
    if (notice) heading.current?.focus();
  }, [notice]);
  const editable = record.status === "draft";
  function open(next: Action, button: HTMLButtonElement) {
    trigger.current = button;
    setAction(next);
  }
  const editor = action && (
    <AlternativeEditor
      decisionId={record.id}
      action={action}
      onChanged={onChanged}
      onReload={onReload}
      onCancel={() => {
        setAction(null);
        // Wait for the trigger to be enabled again before restoring keyboard focus.
        requestAnimationFrame(() => trigger.current?.focus());
      }}
    />
  );
  return (
    <section
      className="live-record-section"
      aria-labelledby="alternatives-heading"
    >
      <div className="record-section-heading">
        <h2 id="alternatives-heading" tabIndex={-1} ref={heading}>
          Alternatives
        </h2>
        <span>{record.alternatives.length}</span>
      </div>
      {notice && (
        <p className="alternative-notice" role="status">
          {notice}
        </p>
      )}
      {editable ? (
        <div className="alternative-intro">
          <p className="field-help">
            Set out the options while this decision is a draft.
          </p>
          <Button
            variant="outline"
            disabled={!!action}
            onClick={(event) => open({ kind: "add" }, event.currentTarget)}
          >
            <Plus size={16} aria-hidden="true" />
            Add alternative
          </Button>
        </div>
      ) : (
        <p className="record-empty-note">
          Alternatives are read-only because this decision is no longer a draft.
        </p>
      )}
      {action?.kind === "add" && editor}
      {record.alternatives.length === 0 && (
        <p className="record-empty-note">
          No alternatives have been added to this decision yet.
        </p>
      )}
      {record.alternatives.map((alternative) => (
        <article
          className="saved-alternative"
          key={alternative.id}
          aria-labelledby={`alternative-${alternative.id}`}
        >
          <div className="eyebrow">
            ALTERNATIVE {alternative.position + 1}
            {record.selected_alternative_id === alternative.id && " · SELECTED"}
          </div>
          <h3 id={`alternative-${alternative.id}`}>{alternative.title}</h3>
          <p>{alternative.description}</p>
          {editable && (
            <div className="alternative-actions">
              <Button
                size="sm"
                variant="outline"
                disabled={!!action}
                onClick={(event) =>
                  open({ kind: "edit", alternative }, event.currentTarget)
                }
              >
                Edit alternative
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={!!action}
                onClick={(event) =>
                  open({ kind: "remove", alternative }, event.currentTarget)
                }
              >
                Remove alternative
              </Button>
            </div>
          )}
          {action &&
            action.kind !== "add" &&
            action.alternative.id === alternative.id &&
            editor}
          {alternative.evidence.length === 0 ? (
            <p className="field-help">No linked evidence.</p>
          ) : (
            <ul className="saved-evidence">
              {alternative.evidence.map((evidence) => (
                <li key={evidence.id}>
                  <span className="eyebrow">
                    {evidence.evidence_type === "supporting"
                      ? "SUPPORTING"
                      : "OPPOSING"}{" "}
                    EVIDENCE
                  </span>
                  <blockquote>{evidence.text}</blockquote>
                  <p className="evidence-source">
                    {evidence.citation.document_title} ·{" "}
                    {evidence.citation.file_name} · Version{" "}
                    {evidence.citation.version_number}, page{" "}
                    {evidence.citation.page_number}
                  </p>
                  {evidence.relevance_note && <p>{evidence.relevance_note}</p>}
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </section>
  );
}
