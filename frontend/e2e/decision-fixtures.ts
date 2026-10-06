export const user = {
  id: "bfe2a1af-ff66-4ef2-b5e9-397519328b87",
  email: "reviewer@example.test",
  display_name: "Decision Reviewer",
  status: "active",
};
export const decision = {
  id: "32cd9e2e-c626-450e-9f00-7b3c89b3ecb2",
  title: "Cooling pressure limit",
  question: "Should the maximum cooling-system pressure be reduced?",
  status: "draft",
  created_at: "2026-10-04T10:00:00Z",
  updated_at: "2026-10-04T10:00:00Z",
  created_by_user_id: user.id,
  decided_by_user_id: null,
};
export const record = {
  ...decision,
  selected_alternative_id: null,
  rationale: null,
  submitted_at: null,
  decided_at: null,
  cancelled_at: null,
  superseded_at: null,
  alternatives: [],
  history: { total: 1, url: `/decisions/${decision.id}/history` },
};
