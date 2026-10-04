import type { ReactNode } from "react";
import { Link } from "react-router";
import { Layers, LockKeyhole } from "lucide-react";

export function AuthLayout({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main className="login-page">
      <section className="login-story" aria-label="About the workspace">
        <Link to="/preview" className="brand">
          <span className="brand-symbol">
            <Layers size={25} strokeWidth={1.4} />
          </span>
          <span>
            Decision<span className="brand-second">workspace</span>
          </span>
        </Link>
        <div>
          <span className="eyebrow">FROM EVIDENCE TO OUTCOME</span>
          <h1>
            Clear thinking.
            <br />
            <em>A lasting record.</em>
          </h1>
          <p>Keep the source, the alternatives, and the reasoning together.</p>
          <div className="login-trail">
            <span>01 &nbsp; SOURCE</span>
            <span>02 &nbsp; REASON</span>
            <span>03 &nbsp; DECIDE</span>
          </div>
        </div>
        <span className="login-edition">KNOWLEDGE & DECISION PLATFORM</span>
      </section>
      <section className="login-panel" aria-labelledby="auth-title">
        <div className="login-form-wrap">
          <span className="eyebrow">
            <LockKeyhole size={14} /> YOUR WORKSPACE
          </span>
          <h2 id="auth-title">{title}</h2>
          <p className="login-description">{description}</p>
          {children}
        </div>
      </section>
    </main>
  );
}
