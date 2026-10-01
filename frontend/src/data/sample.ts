export type Source = {
  id: string;
  title: string;
  reference: string;
  version: string;
  page: number;
  section: string;
  excerpt: string;
  kind: "Specification" | "Review note";
  date: string;
};

export const sources: Source[] = [
  {
    id: "cooling-spec",
    title: "Cooling system specification",
    reference: "ENG-CS-014",
    version: "v3",
    page: 12,
    section: "4.2  Operating pressure",
    kind: "Specification",
    date: "28 Sep 2026",
    excerpt:
      "The cooling circuit shall operate at a maximum continuous pressure of 6 bar. A lower operating limit is recommended where transient pressure excursions may reduce the available safety margin.",
  },
  {
    id: "safety-review",
    title: "Pressure transient review",
    reference: "REV-2026-038",
    version: "v1",
    page: 4,
    section: "2.1  Review findings",
    kind: "Review note",
    date: "29 Sep 2026",
    excerpt:
      "Observed cooling pressure transients approach the current operating limit during pump changeover. Reducing the nominal set point would increase the margin without changing the required cooling duty.",
  },
  {
    id: "electrical-spec",
    title: "Electrical isolation procedure",
    reference: "ENG-EL-008",
    version: "v2",
    page: 7,
    section: "3.0  Isolation sequence",
    kind: "Specification",
    date: "24 Sep 2026",
    excerpt:
      "Before servicing the circulation pump, isolate the electrical supply, verify the absence of voltage, and record the lockout reference in the maintenance register.",
  },
];

export const initialRationale =
  "Reduce the operating pressure limit to provide more headroom during pump changeover. The specification and transient review support this adjustment while maintaining the required cooling duty.";

export const history = [
  {
    title: "Decision submitted for review",
    detail:
      "Two alternatives and two supporting sources are ready for assessment.",
    time: "Today, 09:42",
    actor: "Avery Reed",
  },
  {
    title: "Evidence linked to alternative B",
    detail: "Pressure transient review · v1 · page 4",
    time: "Today, 09:36",
    actor: "Avery Reed",
  },
  {
    title: "Evidence linked to alternative B",
    detail: "Cooling system specification · v3 · page 12",
    time: "Today, 09:31",
    actor: "Avery Reed",
  },
  {
    title: "Alternatives added",
    detail: "Keep the current limit / Reduce the operating limit",
    time: "Yesterday, 16:18",
    actor: "Avery Reed",
  },
  {
    title: "Decision created",
    detail: "Cooling-system operating pressure",
    time: "Yesterday, 16:04",
    actor: "Avery Reed",
  },
];
