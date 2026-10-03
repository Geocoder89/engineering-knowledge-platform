import { useRef, type ComponentProps } from "react";
import * as Primitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
export const Dialog = Primitive.Root;
export function DialogContent({
  className,
  children,
  onOpenAutoFocus,
  onCloseAutoFocus,
  ...props
}: ComponentProps<typeof Primitive.Content>) {
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-50 bg-black/45" />
      <Primitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 grid max-h-[92dvh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 overflow-y-auto rounded-lg border bg-background p-6 shadow-xl",
          className,
        )}
        onOpenAutoFocus={(event) => {
          opener.current =
            document.activeElement instanceof HTMLElement
              ? document.activeElement
              : null;
          onOpenAutoFocus?.(event);
        }}
        onCloseAutoFocus={(event) => {
          onCloseAutoFocus?.(event);
          if (!event.defaultPrevented) {
            event.preventDefault();
            const target = opener.current;
            if (target?.isConnected && !target.matches(":disabled"))
              target.focus();
            else document.getElementById("main-content")?.focus();
          }
        }}
        {...props}
      >
        {children}
        <Primitive.Close className="absolute right-3 top-3 rounded-sm p-1 text-muted-foreground hover:bg-accent">
          <X size={18} />
          <span className="sr-only">Close dialog</span>
        </Primitive.Close>
      </Primitive.Content>
    </Primitive.Portal>
  );
}
export function DialogHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div className={cn("flex flex-col gap-2 pr-4", className)} {...props} />
  );
}
export function DialogTitle({
  className,
  ...props
}: ComponentProps<typeof Primitive.Title>) {
  return (
    <Primitive.Title
      className={cn("text-xl font-medium leading-tight", className)}
      {...props}
    />
  );
}
export function DialogDescription({
  className,
  ...props
}: ComponentProps<typeof Primitive.Description>) {
  return (
    <Primitive.Description
      className={cn("text-sm leading-relaxed text-muted-foreground", className)}
      {...props}
    />
  );
}
