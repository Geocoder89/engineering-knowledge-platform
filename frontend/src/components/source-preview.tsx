import { ArrowUpRight, FileText, Quote } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Source } from "@/data/sample";

export function SourcePreview({
  source,
  onClose,
}: {
  source: Source | null;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={Boolean(source)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="source-dialog">
        <DialogHeader>
          <div className="eyebrow">
            <FileText size={14} /> SOURCE EXCERPT
          </div>
          <DialogTitle>{source?.title}</DialogTitle>
          <DialogDescription>
            {source?.reference} · {source?.version} · page {source?.page}
          </DialogDescription>
        </DialogHeader>
        <div className="source-paper">
          <div className="paper-masthead">
            <span>ENGINEERING / TECHNICAL RECORD</span>
            <span>{source?.reference}</span>
          </div>
          <h3>{source?.section}</h3>
          <p className="paper-context">
            Operating requirements and review findings for the engineering
            assessment.
          </p>
          <blockquote>
            <Quote size={21} aria-hidden="true" />
            {source?.excerpt}
          </blockquote>
          <div className="paper-rule" />
          <div className="paper-rule short" />
          <footer>
            <span>Illustrative sample document</span>
            <span>{String(source?.page).padStart(2, "0")}</span>
          </footer>
        </div>
        <p className="source-disclaimer">
          This preview contains fictional source material for design review. It
          is not an engineering recommendation or a rendered PDF.
        </p>
        <Button variant="outline" onClick={onClose}>
          Return to workspace <ArrowUpRight size={14} />
        </Button>
      </DialogContent>
    </Dialog>
  );
}
