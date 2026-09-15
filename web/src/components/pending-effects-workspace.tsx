"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { ConfirmationDialog } from "@/components/confirmation-dialog";
import { PageHeader } from "@/components/page-header";
import { PendingStatusBadge, RouteBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { ApiError, cancelPendingEffect, getPendingEffects } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/format";
import type { PendingEffectCompactView, PendingStatus } from "@/lib/types";

type PendingFilter = "ALL" | PendingStatus;

const filters: PendingFilter[] = [
  "ALL",
  "PENDING",
  "SETTLING",
  "SETTLED",
  "CANCELLED",
  "FAILED",
];

function filterLabel(filter: PendingFilter) {
  return filter === "ALL" ? "All" : filter.charAt(0) + filter.slice(1).toLowerCase();
}

function raceMessage(reason: string) {
  return {
    already_settling: "Settlement claimed this effect before cancellation. The latest state is shown.",
    already_settled: "This effect settled before cancellation. The latest state is shown.",
    already_cancelled: "This effect was already cancelled.",
    already_failed: "This effect had already failed and cannot be cancelled.",
  }[reason] ?? "Cancellation did not change the effect. The latest state is shown.";
}

export function PendingEffectsWorkspace() {
  const [filter, setFilter] = useState<PendingFilter>("ALL");
  const [selectedEffect, setSelectedEffect] = useState<PendingEffectCompactView | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);
  const loader = useCallback(
    (signal?: AbortSignal) => getPendingEffects(filter === "ALL" ? undefined : filter, signal),
    [filter],
  );
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 5_000);

  const cancel = async () => {
    if (!selectedEffect) return;
    setSubmitting(true);
    setMutationMessage(null);
    try {
      const result = await cancelPendingEffect(selectedEffect.effect_id);
      setMutationMessage(
        result.cancelled
          ? "Cancellation was confirmed by the authoritative backend."
          : raceMessage(result.reason),
      );
      setSelectedEffect(null);
      await refresh();
    } catch (mutationError) {
      setMutationMessage(
        mutationError instanceof ApiError && mutationError.status === 404
          ? "This effect no longer exists in the current runtime."
          : mutationError instanceof Error
            ? mutationError.message
            : "Cancellation failed. The effect was not changed by the UI.",
      );
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Attention"
        title="Pending Effects"
        description="Monitor reversible YELLOW actions while the backend owns their settlement and cancellation lifecycle."
        action={<div className="flex items-center gap-3"><Badge className="border-violet/20 bg-violet-soft text-violet">Local Demo Coordinator</Badge><Button variant="outline" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "Refresh effects"}</Button></div>}
      />

      <div className="mb-4 flex flex-wrap gap-2" aria-label="Filter pending effects">
        {filters.map((item) => (
          <Button key={item} size="sm" variant={filter === item ? "default" : "outline"} aria-pressed={filter === item} onClick={() => { setFilter(item); setMutationMessage(null); }}>
            {filterLabel(item)}
          </Button>
        ))}
      </div>

      {mutationMessage && <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800" role="status" aria-live="polite">{mutationMessage}</div>}

      {loading && !data ? (
        <div className="space-y-3" aria-label="Loading pending effects"><Skeleton className="h-32 rounded-xl" /><Skeleton className="h-32 rounded-xl" /><Skeleton className="h-32 rounded-xl" /></div>
      ) : !data ? (
        <ErrorState message={error ?? "Pending effects could not be loaded."} retry={() => void refresh()} />
      ) : data.length === 0 ? (
        <EmptyState title="No actions are waiting to settle." description={filter === "ALL" ? "The current runtime has no pending-effect history." : `No effects have ${filterLabel(filter).toLowerCase()} status.`} />
      ) : (
        <div className="space-y-3">
          {error && <StaleNotice message={error} />}
          {data.map((effect) => (
            <Card key={effect.effect_id} id={effect.effect_id} className="scroll-mt-24">
              <CardContent className="grid gap-4 pt-5 md:grid-cols-[150px_minmax(0,1fr)_220px_auto] md:items-center">
                <div className="flex flex-wrap items-center gap-2"><RouteBadge route="YELLOW" /><PendingStatusBadge status={effect.status} /></div>
                <div>
                  <p className="font-semibold text-foreground">{effect.description}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Created {formatRelativeTime(effect.created_at)} · {effect.effect_type.replaceAll("_", " ")}</p>
                  {effect.related_shift && <Link className="mt-2 inline-flex text-xs font-semibold text-primary hover:underline" href={`/shifts/${effect.related_shift.shift_id}`}>{effect.related_shift.site_name} →</Link>}
                  {effect.result_summary && <p className="mt-2 text-xs font-medium text-green">{effect.result_summary}</p>}
                  {effect.failure_summary && <p className="mt-2 text-xs font-medium text-red">{effect.failure_summary}</p>}
                </div>
                <div className="text-sm">
                  <p className="text-xs text-muted-foreground">Settlement window</p>
                  <p className="mt-1 font-medium">{effect.status === "PENDING" ? `Settles ${formatRelativeTime(effect.settle_at)}` : `Scheduled ${formatDateTime(effect.settle_at)}`}</p>
                  {effect.settled_at && <p className="mt-1 text-xs text-muted-foreground">Completed {formatRelativeTime(effect.settled_at)}</p>}
                </div>
                <div className="md:text-right">
                  {effect.can_cancel ? (
                    <Button variant="outline" disabled={submitting} aria-label={`Cancel ${effect.description}`} onClick={() => setSelectedEffect(effect)}>Cancel effect</Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">No action available</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ConfirmationDialog
        open={selectedEffect !== null}
        title="Cancel this pending effect?"
        description="The backend will cancel only if the effect is still PENDING. If settlement has already won the race, QUORUM will return and display the authoritative state."
        confirmLabel="Confirm cancellation"
        destructive
        busy={submitting}
        onOpenChange={(open) => { if (!open && !submitting) setSelectedEffect(null); }}
        onConfirm={() => void cancel()}
      />
    </>
  );
}
