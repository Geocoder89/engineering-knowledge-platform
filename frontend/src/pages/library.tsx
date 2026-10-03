import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  FileText,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourcePreview } from "@/components/source-preview";
import { sources, type Source } from "@/data/sample";

export function DocumentLibrary() {
  const [filter, setFilter] = useState("All documents");
  const [source, setSource] = useState<Source | null>(null);
  const documents = sources.filter(
    (item) => filter === "All documents" || item.kind === filter,
  );
  return (
    <div className="library-page page-enter">
      <div className="page-heading-row">
        <span className="eyebrow">SOURCE LIBRARY</span>
        <span className="eyebrow">03 DOCUMENTS</span>
      </div>
      <div className="library-intro">
        <div>
          <h1>
            Knowledge, with
            <br />
            <em>its source intact.</em>
          </h1>
          <p className="intro-description">
            Specifications, review notes, and the details
            <br className="desktop-break" /> behind a defensible decision.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link to="/search">
            Explore the evidence <ArrowUpRight size={16} />
          </Link>
        </Button>
      </div>
      <div className="library-toolbar">
        <div
          className="document-filters"
          role="group"
          aria-label="Document type"
        >
          {["All documents", "Specification", "Review note"].map((item) => (
            <button
              key={item}
              aria-pressed={item === filter}
              onClick={() => setFilter(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <span className="small muted" role="status">
          {documents.length} documents
        </span>
      </div>
      <div className="document-table-heading" aria-hidden="true">
        <span>DOCUMENT</span>
        <span>VERSION</span>
        <span>STATUS</span>
        <span>UPDATED</span>
        <span />
      </div>
      <div className="document-list">
        {documents.map((item) => (
          <button
            key={item.id}
            className="document-row"
            aria-label={`Open ${item.title}`}
            onClick={() => setSource(item)}
          >
            <span className="document-name">
              <span className="document-icon">
                <FileText size={22} strokeWidth={1.3} />
              </span>
              <span>
                <strong>{item.title}</strong>
                <small>
                  {item.reference} <span> / </span> {item.kind}
                </small>
              </span>
            </span>
            <span className="document-version">{item.version}</span>
            <span className="document-status">
              <CheckCircle2 size={13} /> Ready
            </span>
            <span className="document-date">{item.date}</span>
            <ArrowUpRight size={17} />
          </button>
        ))}
      </div>
      <div className="library-note">
        <span className="large-number">01—03</span>
        <div>
          <h2>More than a file collection.</h2>
          <p>
            A source becomes useful when you can connect its detail to the
            decision it informed.
          </p>
          <Link to="/decisions/DEC-024">
            Follow an example decision <ArrowRight size={15} />
          </Link>
        </div>
      </div>
      <p className="sample-caption">
        Fictional sample library. Document uploads and processing will be
        connected in a later release.
      </p>
      <SourcePreview source={source} onClose={() => setSource(null)} />
    </div>
  );
}

export function EvidenceSearch() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "cooling pressure";
  const [source, setSource] = useState<Source | null>(null);
  const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const results = words.length
    ? sources.filter((item) =>
        words.every((word) =>
          `${item.title} ${item.excerpt} ${item.reference}`
            .toLowerCase()
            .includes(word),
        ),
      )
    : [];
  return (
    <div className="search-page page-enter">
      <div className="eyebrow">EVIDENCE SEARCH</div>
      <h1>
        Find the passage.
        <br />
        <em>Keep the context.</em>
      </h1>
      <p className="intro-description">
        Start with a question or a phrase.
        <br />
        Follow the result back to its source.
      </p>
      <form
        key={query}
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          setParams({ q: String(data.get("query") ?? "").trim() });
        }}
      >
        <Search size={22} strokeWidth={1.5} />
        <label className="sr-only" htmlFor="search-query">
          Search sample library
        </label>
        <input
          id="search-query"
          name="query"
          type="search"
          defaultValue={query}
          placeholder="Search the sample library…"
          maxLength={500}
        />
        <Button type="submit">
          Search <ArrowRight size={16} />
        </Button>
      </form>
      <div className="search-suggestions">
        <span>TRY A TOPIC</span>
        {["Cooling pressure", "Pump changeover", "Electrical isolation"].map(
          (topic) => (
            <button
              key={topic}
              onClick={() => setParams({ q: topic.toLowerCase() })}
            >
              {topic}
              <ArrowUpRight size={12} />
            </button>
          ),
        )}
      </div>
      <div className="search-results-heading">
        <span role="status">
          {results.length} {results.length === 1 ? "passage" : "passages"}
          {query.trim() && (
            <>
              {" "}
              for <strong>“{query}”</strong>
            </>
          )}
        </span>
        <span className="eyebrow">SAMPLE TEXT SEARCH</span>
      </div>
      <div className="search-results">
        {results.map((item, index) => (
          <article key={item.id} className="search-result">
            <span className="result-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <div className="result-citation">
                {item.reference} <span> / </span> {item.version}{" "}
                <span> / </span> PAGE {item.page}
              </div>
              <h2>{item.title}</h2>
              <p>{item.excerpt}</p>
              <button className="text-action" onClick={() => setSource(item)}>
                Inspect source excerpt <ArrowUpRight size={15} />
              </button>
            </div>
          </article>
        ))}
      </div>
      {!results.length && (
        <div className="empty-state">
          <Search size={28} />
          <h2>No matching passages.</h2>
          <p>
            Try a topic from this small sample library, such as cooling or
            electrical isolation.
          </p>
          <Button variant="outline" onClick={() => setParams({ q: "cooling" })}>
            Search cooling
          </Button>
        </div>
      )}
      <p className="sample-caption">
        This preview searches local sample text. Semantic search and real
        document results will use the backend in a later release.
      </p>
      <SourcePreview source={source} onClose={() => setSource(null)} />
    </div>
  );
}
