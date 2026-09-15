"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import { ConfirmationDialog } from "@/components/confirmation-dialog";
import { PageHeader } from "@/components/page-header";
import { HumanDecisionStatusBadge, RouteBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import {
  ApiError,
  getHumanDecision,
  getHumanDecisions,
  resolveHumanDecision,
} from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/format";
import type {
  HumanDecisionAction,
  HumanDecisionSummary,
  InterruptStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type QueueFilter = "ALL" | InterruptStatus;

const queueFilters: { value: QueueFilter; label: string }[] = [
  { value: "OPEN", label: "Needs decision" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "ALL", label: "All" },
];

const actionLabels: Record<HumanDecisionAction, string> = {
  APPROVE: "Approve",
  VETO: "Veto",
};

function QueueItem({
  item,
  selected,
  onSelect,
}: {
  item: HumanDecisionSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-xl border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "border-red/30 bg-red-soft/50"
          : "border-border bg-white hover:border-blue-200 hover:bg-blue-50/30",
      )}
      aria-pressed={selected}
    >
      <div className="flex items-center justify-between gap-3">
        <HumanDecisionStatusBadge status={item.status} />
        <span className="text-xs text-muted-foreground">{formatRelativeTime(item.created_at)}</span>
      </div>
      <p className="mt-3 text-sm font-semibold text-foreground">{item.title}</p>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{item.reason}</p>
      {item.shift && <p className="mt-3 text-xs font-semibold text-primary">{item.shift.site_name}</p>}
    </button>
  );
}

function DecisionDetailPanel({
  decisionId,
  onResolved,
}: {
  decisionId: string;
  onResolved: (decisionId: string) => void;
}) {
  const loader = useCallback(
    (signal?: AbortSignal) => getHumanDecision(decisionId, signal),
    [decisionId],
  );
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 5_000);
  const [note, setNote] = useState("");
  const [confirmAction, setConfirmAction] = useState<HumanDecisionAction | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mutationMessage, setMutationMessage] = useState<string | null>(null);

  const submit = async () => {
    if (!confirmAction || !data) return;
    setSubmitting(true);
    setMutationMessage(null);
    try {
      const result = await resolveHumanDecision(data.interrupt_id, {
        action: confirmAction,
        note: note.trim() || null,
        actor: "demo-coordinator",
        expected_version: data.version,
      });
      setConfirmAction(null);
      setMutationMessage(
        result.automatic_continuation
          ? "Decision recorded and the workflow continued."
          : "Decision recorded. Automatic workflow continuation is not wired in this local phase.",
      );
      await refresh();
      onResolved(decisionId);
    } catch (mutationError) {
      if (mutationError instanceof ApiError && mutationError.status === 409) {
        setMutationMessage("Another action changed this decision. The authoritative state has been reloaded.");
        await refresh();
        onResolved(decisionId);
      } else {
        setMutationMessage(
          mutationError instanceof Error
            ? mutationError.message
            : "The decision could not be submitted. It remains unresolved.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !data) {
    return <div className="grid gap-5 lg:grid-cols-[1fr_320px]"><Skeleton className="h-[560px] rounded-xl" /><Skeleton className="h-[420px] rounded-xl" /></div>;
  }
  if (!data) {
    return <ErrorState message={error ?? "Human decisions could not be loaded."} retry={() => void refresh()} />;
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-5">
        {error && <StaleNotice message={error} />}
        <Card className={data.status === "OPEN" ? "border-red/20" : undefined}>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <RouteBadge route={data.route} />
                <HumanDecisionStatusBadge status={data.status} />
              </div>
              <span className="text-xs text-muted-foreground">Version {data.version}</span>
            </div>
            <CardTitle className="pt-3 text-xl">{data.title}</CardTitle>
            <CardDescription>{data.reason}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-xl border border-red/15 bg-red-soft/40 p-4">
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-red">Why QUORUM stopped</p>
              <p className="mt-2 text-sm leading-6 text-foreground">
                No consequential action was taken pending an explicit coordinator decision.
              </p>
            </div>

            {data.status === "OPEN" ? (
              <div className="mt-5">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-sm font-semibold" htmlFor={`decision-note-${data.interrupt_id}`}>Optional coordinator note</label>
                  <span className="text-xs text-muted-foreground">{note.length}/1000</span>
                </div>
                <Textarea
                  id={`decision-note-${data.interrupt_id}`}
                  className="mt-2"
                  maxLength={1000}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Add concise context for the audit record."
                  disabled={submitting}
                />
                <div className="mt-4 flex flex-wrap gap-3">
                  {data.allowed_actions.map((action) => (
                    <Button
                      key={action}
                      variant={action === "VETO" ? "destructive" : "default"}
                      disabled={submitting || refreshing}
                      onClick={() => setConfirmAction(action)}
                    >
                      {actionLabels[action]}
                    </Button>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">Actions are supplied by the backend. This local demo has no authenticated identity.</p>
              </div>
            ) : data.resolution ? (
              <div className="mt-5 rounded-xl border border-green/20 bg-green-soft/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-semibold">{actionLabels[data.resolution.action]} recorded</p>
                  <span className="text-xs text-muted-foreground">{formatDateTime(data.resolution.resolved_at)}</span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">Actor: Local Demo Coordinator</p>
                {data.resolution.note && <p className="mt-2 text-sm leading-6">“{data.resolution.note}”</p>}
                {!data.resolution.automatic_continuation && (
                  <p className="mt-3 text-xs font-medium text-amber">Decision state is resolved; automatic agent continuation is not wired.</p>
                )}
              </div>
            ) : (
              <p className="mt-5 text-sm text-muted-foreground">This record is already resolved. Historical resolution details were not recorded by the earlier runtime.</p>
            )}

            {mutationMessage && (
              <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800" role="status" aria-live="polite">
                {mutationMessage}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Policy evidence</CardTitle><CardDescription>Sanitized evidence retained by the deterministic routing layer.</CardDescription></CardHeader>
          <CardContent>
            {data.evidence.length === 0 ? (
              <EmptyState title="No structured evidence available" description="The earlier runtime did not retain a safe structured explanation for this record." />
            ) : (
              <dl className="grid gap-3 sm:grid-cols-2">
                {data.evidence.map((item) => (
                  <div className="rounded-xl border border-border p-4" key={item.label}>
                    <dt className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">{item.label}</dt>
                    <dd className="mt-2 text-sm font-medium">{item.value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </CardContent>
        </Card>
      </div>

      <aside className="space-y-5">
        <Card>
          <CardHeader><CardTitle className="text-base">Coordinator context</CardTitle></CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div><p className="text-xs text-muted-foreground">Acting identity</p><p className="mt-1 font-semibold">Local Demo Coordinator</p></div>
            <div><p className="text-xs text-muted-foreground">Created</p><p className="mt-1 font-medium">{formatDateTime(data.created_at)}</p></div>
            <div><p className="text-xs text-muted-foreground">Attention Budget</p><p className="mt-1 font-medium">{data.attention_override ? "Layer-0 override" : data.attention_spent ? "One interruption spent" : "No recorded budget change"}</p></div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Related operation</CardTitle></CardHeader>
          <CardContent className="space-y-4 text-sm">
            {data.shift ? (
              <div><p className="font-semibold">{data.shift.site_name}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(data.shift.starts_at)}</p><Link className="mt-3 inline-flex text-sm font-semibold text-primary hover:underline" href={`/shifts/${data.shift.shift_id}`}>Open shift →</Link></div>
            ) : <p className="text-muted-foreground">No shift context is safely available.</p>}
            {data.volunteer && <div className="border-t border-border pt-4"><p className="text-xs text-muted-foreground">Volunteer</p><p className="mt-1 font-medium">{data.volunteer.display_name}</p></div>}
            {data.negotiation && <div className="border-t border-border pt-4"><p className="text-xs text-muted-foreground">Negotiation status</p><Badge className="mt-2">{data.negotiation.status.replaceAll("_", " ")}</Badge></div>}
          </CardContent>
        </Card>
      </aside>

      <ConfirmationDialog
        open={confirmAction !== null}
        title={confirmAction ? `${actionLabels[confirmAction]} this decision?` : "Confirm decision"}
        description="This records a consequential coordinator action in the authoritative backend. It does not imply that an agent workflow resumed unless the server confirms that outcome."
        confirmLabel={confirmAction ? `Confirm ${actionLabels[confirmAction]}` : "Confirm"}
        destructive={confirmAction === "VETO"}
        busy={submitting}
        onOpenChange={(open) => { if (!open && !submitting) setConfirmAction(null); }}
        onConfirm={() => void submit()}
      />
    </div>
  );
}

export function HumanDecisionsWorkspace({ initialDecisionId }: { initialDecisionId?: string }) {
  const [filter, setFilter] = useState<QueueFilter>("OPEN");
  const [selected, setSelected] = useState<string | null>(initialDecisionId ?? null);
  const loader = useCallback(
    (signal?: AbortSignal) => getHumanDecisions(filter === "ALL" ? undefined : filter, signal),
    [filter],
  );
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 5_000);
  const selectedId = selected ?? data?.[0]?.interrupt_id ?? null;

  return (
    <>
      <PageHeader
        eyebrow="Attention"
        title="Human Decision Center"
        description="Review RED cases QUORUM cannot safely decide alone. Allowed actions and evidence come from the backend."
        action={<div className="flex items-center gap-3"><Badge className="border-violet/20 bg-violet-soft text-violet">Local Demo Coordinator</Badge><Button variant="outline" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "Refresh queue"}</Button></div>}
      />
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside>
          <div className="mb-3 flex flex-wrap gap-2" aria-label="Filter human decisions">
            {queueFilters.map((item) => <Button key={item.value} size="sm" variant={filter === item.value ? "default" : "outline"} aria-pressed={filter === item.value} onClick={() => { setFilter(item.value); setSelected(null); }}>{item.label}</Button>)}
          </div>
          {loading && !data ? (
            <div className="space-y-3"><Skeleton className="h-36 rounded-xl" /><Skeleton className="h-36 rounded-xl" /></div>
          ) : !data ? (
            <ErrorState message={error ?? "Human decisions could not be loaded."} retry={() => void refresh()} />
          ) : data.length === 0 ? (
            <EmptyState title="No human decisions require attention." description={filter === "OPEN" ? "QUORUM has no unresolved RED cases." : "No decisions match this queue filter."} />
          ) : (
            <div className="space-y-3">{error && <StaleNotice message={error} />}{data.map((item) => <QueueItem key={item.interrupt_id} item={item} selected={selectedId === item.interrupt_id} onSelect={() => setSelected(item.interrupt_id)} />)}</div>
          )}
        </aside>
        <section aria-label="Selected human decision">
          {selectedId ? <DecisionDetailPanel key={selectedId} decisionId={selectedId} onResolved={(decisionId) => { setSelected(decisionId); void refresh(); }} /> : <EmptyState title="Select a human decision" description="Choose a RED case from the queue to inspect its backend-provided evidence and allowed actions." />}
        </section>
      </div>
    </>
  );
}
