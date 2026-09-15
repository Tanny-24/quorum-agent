"use client";

import { useEffect, useId, useRef } from "react";

import { Button } from "@/components/ui/button";

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  destructive = false,
  onConfirm,
  onOpenChange,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  destructive?: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="m-auto w-[min(92vw,480px)] rounded-2xl border border-border bg-white p-0 text-foreground shadow-2xl backdrop:bg-slate-950/45"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !busy) {
          event.preventDefault();
          onOpenChange(false);
        }
      }}
      onCancel={(event) => {
        if (busy) event.preventDefault();
        else onOpenChange(false);
      }}
      onClose={() => {
        if (open && !busy) onOpenChange(false);
      }}
    >
      <div className="p-6">
        <h2 className="text-lg font-bold text-navy" id={titleId}>{title}</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground" id={descriptionId}>{description}</p>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button autoFocus variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>
            Keep reviewing
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            disabled={busy}
            aria-busy={busy}
            onClick={onConfirm}
          >
            {busy ? "Submitting…" : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
