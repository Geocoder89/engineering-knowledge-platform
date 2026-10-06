import { ApiError } from "./api";
export const statusLabels = {
  draft: "Draft",
  in_review: "In review",
  decided: "Decided",
  cancelled: "Cancelled",
  superseded: "Superseded",
};
export type DecisionStatus = keyof typeof statusLabels;
export type Decision = {
  id: string;
  title: string;
  question: string;
  status: DecisionStatus;
  created_at: string;
  updated_at: string;
  created_by_user_id: string | null;
  decided_by_user_id: string | null;
};
export type DecisionList = {
  items: Decision[];
  total: number;
  offset: number;
  limit: number;
};
type Evidence = {
  id: string;
  evidence_type: "supporting" | "opposing";
  text: string;
  relevance_note: string | null;
  citation: {
    document_title: string;
    file_name: string;
    version_number: number;
    page_number: number;
  };
};
export type Alternative = {
  id: string;
  title: string;
  description: string;
  position: number;
  evidence: Evidence[];
};
export type DecisionRecord = Decision & {
  selected_alternative_id: string | null;
  rationale: string | null;
  submitted_at: string | null;
  decided_at: string | null;
  cancelled_at: string | null;
  superseded_at: string | null;
  alternatives: Alternative[];
  history: { total: number };
};
export function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i.test(value)
  );
}
function invalid(): never {
  throw new ApiError(
    "The service returned an incomplete decision record. Please try again.",
  );
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    return invalid();
  return value as Record<string, unknown>;
}
function string(value: unknown): string {
  return typeof value === "string" ? value : invalid();
}
function uuid(value: unknown): string {
  return isUuid(value) ? value : invalid();
}
function nullableString(value: unknown): string | null {
  return value === null ? null : string(value);
}
function nullableUuid(value: unknown): string | null {
  return value === null ? null : uuid(value);
}
function integer(value: unknown, minimum = 0): number {
  return typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum
    ? value
    : invalid();
}
function date(value: unknown): string {
  const result = string(value);
  return Number.isFinite(Date.parse(result)) ? result : invalid();
}
function nullableDate(value: unknown): string | null {
  return value === null ? null : date(value);
}
function array<T>(value: unknown, parse: (item: unknown) => T): T[] {
  return Array.isArray(value) ? value.map(parse) : invalid();
}
export function parseDecision(value: unknown): Decision {
  const data = object(value);
  const status = string(data.status);
  if (!Object.hasOwn(statusLabels, status)) return invalid();
  return {
    id: uuid(data.id),
    title: string(data.title),
    question: string(data.question),
    status: status as DecisionStatus,
    created_at: date(data.created_at),
    updated_at: date(data.updated_at),
    created_by_user_id: nullableUuid(data.created_by_user_id),
    decided_by_user_id: nullableUuid(data.decided_by_user_id),
  };
}
export function parseDecisionList(value: unknown): DecisionList {
  const data = object(value);
  return {
    items: array(data.items, parseDecision),
    total: integer(data.total),
    offset: integer(data.offset),
    limit: integer(data.limit, 1),
  };
}
function parseEvidence(value: unknown): Evidence {
  const data = object(value),
    citation = object(data.citation);
  if (data.evidence_type !== "supporting" && data.evidence_type !== "opposing")
    return invalid();
  return {
    id: uuid(data.id),
    evidence_type: data.evidence_type,
    text: string(data.text),
    relevance_note: nullableString(data.relevance_note),
    citation: {
      document_title: string(citation.document_title),
      file_name: string(citation.file_name),
      version_number: integer(citation.version_number, 1),
      page_number: integer(citation.page_number, 1),
    },
  };
}
export function parseDecisionRecord(value: unknown): DecisionRecord {
  const data = object(value);
  return {
    ...parseDecision(value),
    selected_alternative_id: nullableUuid(data.selected_alternative_id),
    rationale: nullableString(data.rationale),
    submitted_at: nullableDate(data.submitted_at),
    decided_at: nullableDate(data.decided_at),
    cancelled_at: nullableDate(data.cancelled_at),
    superseded_at: nullableDate(data.superseded_at),
    history: { total: integer(object(data.history).total) },
    alternatives: array(data.alternatives, (value) => {
      const item = object(value);
      return {
        id: uuid(item.id),
        title: string(item.title),
        description: string(item.description),
        position: integer(item.position),
        evidence: array(item.evidence, parseEvidence),
      };
    }),
  };
}
export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
