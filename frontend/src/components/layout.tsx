import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import {
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  FileText,
  Layers,
  Menu,
  Search,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function Layout() {
  const [aboutOpen, setAboutOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const panel = menuRef.current;
    const menuButton = menuButtonRef.current;
    const links = () =>
      Array.from(panel?.querySelectorAll<HTMLElement>("a,button") ?? []);
    links()[0]?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
      if (event.key !== "Tab") return;
      const controls = links();
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    const desktop = window.matchMedia("(min-width: 721px)");
    const handleResize = () => {
      if (desktop.matches) setMenuOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    desktop.addEventListener("change", handleResize);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      desktop.removeEventListener("change", handleResize);
      document.body.style.overflow = previousOverflow;
      menuButton?.focus();
    };
  }, [menuOpen]);
  const location = useLocation();
  const section = location.pathname.startsWith("/preview/decisions")
    ? "Decisions"
    : location.pathname === "/preview/documents"
      ? "Documents"
      : "Search";
  const closeMenu = () => setMenuOpen(false);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {menuOpen && (
        <button
          className="nav-backdrop"
          aria-label="Close navigation"
          onClick={closeMenu}
        />
      )}
      <aside
        ref={menuRef}
        role={menuOpen ? "dialog" : undefined}
        aria-modal={menuOpen ? true : undefined}
        className={`sidebar ${menuOpen ? "is-open" : ""}`}
        aria-label="Workspace navigation"
      >
        <Link
          className="brand"
          to="/preview/decisions/DEC-024"
          onClick={closeMenu}
        >
          <span className="brand-symbol">
            <Layers size={25} strokeWidth={1.4} />
          </span>
          <span>
            Decision<span className="brand-second">workspace</span>
          </span>
        </Link>
        <button
          className="mobile-close"
          aria-label="Close navigation"
          onClick={closeMenu}
        >
          <X size={22} />
        </button>
        <div className="workspace-label">
          <span className="workspace-mark">E</span>
          <div>
            Engineering workspace<small>Sample project</small>
          </div>
        </div>
        <div className="nav-heading">WORKSPACE</div>
        <nav>
          <NavLink to="/preview/decisions/DEC-024" onClick={closeMenu}>
            <Layers size={17} /> Decisions <span className="nav-count">01</span>
          </NavLink>
          <NavLink to="/preview/documents" onClick={closeMenu}>
            <FileText size={17} /> Documents{" "}
            <span className="nav-count">03</span>
          </NavLink>
          <NavLink to="/preview/search" onClick={closeMenu}>
            <Search size={17} /> Search
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <ArrowDownRight size={23} strokeWidth={1.3} />
          <p>
            Good decisions
            <br />
            leave a clear trail.
          </p>
          <span>From source to rationale.</span>
        </div>
        <div className="sidebar-bottom">
          <Link className="preview-link" to="/workspace" onClick={closeMenu}>
            Your account <ArrowUpRight size={13} />
          </Link>
          <button
            className="preview-link"
            onClick={() => {
              setMenuOpen(false);
              setAboutOpen(true);
            }}
          >
            <BookOpen size={16} /> About this preview <ArrowUpRight size={13} />
          </button>
          <div className="profile">
            <span className="avatar">AR</span>
            <div>
              Avery Reed<small>Example engineer</small>
            </div>
            <span className="sample-dot" />
          </div>
        </div>
      </aside>
      <div className="app-body" inert={menuOpen}>
        <header className="topbar">
          <button
            ref={menuButtonRef}
            className="mobile-menu"
            aria-label="Open navigation"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumbs">
            <span>Workspace</span>
            <ChevronRight size={13} />
            <span>{section}</span>
            {section === "Decisions" && (
              <>
                <ChevronRight size={13} />
                <strong>DEC-024</strong>
              </>
            )}
          </div>
          <button
            className="preview-indicator"
            onClick={() => {
              setMenuOpen(false);
              setAboutOpen(true);
            }}
          >
            <span /> Interactive preview
          </button>
        </header>
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>KNOWLEDGE & DECISION PLATFORM</span>
          <span>Sample content · Changes reset when you leave</span>
        </footer>
      </div>
      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>A working design preview</DialogTitle>
            <DialogDescription>
              Explore the interface with fictional engineering records.
            </DialogDescription>
          </DialogHeader>
          <p className="dialog-copy">
            Compare alternatives, inspect source excerpts, edit the example
            rationale, and search the sample library. Changes are temporary and
            reset when you leave the decision screen or refresh.
          </p>
          <p className="dialog-copy">
            This sample workspace uses fictional data. Sign in to access your
            account. No documents are uploaded and no embedding requests are
            made here.
          </p>
          <Button onClick={() => setAboutOpen(false)}>
            Explore the workspace <ArrowUpRight size={15} />
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
