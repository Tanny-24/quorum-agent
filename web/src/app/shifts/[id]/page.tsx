"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { PendingStatusBadge, RouteBadge, ShiftStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getShift } from "@/lib/api";
import { formatDateTime, formatRelativeTime, roleLabel } from "@/lib/format";

function DetailSkeleton() {
  return (
    <div className="grid gap-5 lg:grid-cols-2" aria-label="Loading shift detail">
      <Skeleton className="h-44 rounded-xl lg:col-span-2" />
      <Skeleton className="h-64 rounded-xl" />
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}

export default function ShiftDetailPage() {
  const params = useParams<{ id: string }>();
  const shiftId = params.id;
  const loader = useCallback((signal?: AbortSignal) => getShift(shiftId, signal), [shiftId]);
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 10_000);

  return (
    <>
      <Link href="/shifts" className="mb-4 inline-flex text-sm font-semibold text-primary hover:underline">
        ← Back to shifts
      </Link>
      <PageHeader
        eyebrow="Shift detail"
        title={data?.site_name ?? "Shift operation"}
        description={
          data
            ? `${formatDateTime(data.starts_at)} to ${formatDateTime(data.ends_at)} · Live runtime state refreshes every 10 seconds.`
            : "Coverage, recovery state, and the evidence behind QUORUM’s next action."
        }
        action={
          <Button variant="outline" onClick={() => void refresh()} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh state"}
          </Button>
        }
      />

      {loading && !data ? (
        <DetailSkeleton />
      ) : !data ? (
        <ErrorState message={error ?? "No shift detail was returned."} retry={() => void refresh()} />
      ) : (
        <div className="space-y-5">
          {error && <StaleNotice message={error} />}
          <Card>
            <CardHeader className="flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="text-base">Coverage snapshot</CardTitle>
                <CardDescription className="mt-1">Derived from confirmed assignments and required roles.</CardDescription>
              </div>
              <ShiftStatusBadge status={data.status} />
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {data.coverage.map((coverage) => (
                <div className="rounded-xl border border-border p-4" key={coverage.role}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold">{roleLabel(coverage.role)}</p>
                    <span className="text-sm font-bold tabular-nums">{coverage.assigned}/{coverage.required}</span>
                  </div>
                  <Progress className="mt-3" value={coverage.assigned} max={coverage.required} label={`${roleLabel(coverage.role)} coverage`} />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {coverage.shortfall === 0 ? "Role is fully covered." : `${coverage.shortfall} additional volunteer${coverage.shortfall === 1 ? "" : "s"} needed.`}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Confirmed assignments</CardTitle>
                <CardDescription>Volunteers currently assigned to this shift.</CardDescription>
              </CardHeader>
              <CardContent>
                {data.assignments.length === 0 ? (
                  <EmptyState title="No confirmed assignments" description="Confirmed volunteer assignments will appear here." />
                ) : (
                  <div className="divide-y divide-border">
                    {data.assignments.map((assignment) => (
                      <div className="flex items-center justify-between gap-4 py-3" key={assignment.assignment_id}>
                        <div>
                          <p className="text-sm font-semibold">{assignment.volunteer.display_name}</p>
                          <p className="mt-0.5 text-xs text-muted-foreground">Confirmed {formatRelativeTime(assignment.confirmed_at)}</p>
                        </div>
                        <Badge>{roleLabel(assignment.role)}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Active gaps</CardTitle>
                <CardDescription>Role-level shortages still in the recovery lifecycle.</CardDescription>
              </CardHeader>
              <CardContent>
                {data.gaps.length === 0 ? (
                  <EmptyState title="No active gaps" description="This operation has no unresolved role-level gap record." />
                ) : (
                  <div className="space-y-3">
                    {data.gaps.map((gap) => (
                      <div className="flex items-center justify-between gap-4 rounded-xl border border-amber/20 bg-amber-soft/50 p-4" key={gap.gap_id}>
                        <div>
                          <p className="text-sm font-semibold">{roleLabel(gap.role)} shortfall: {gap.shortfall}</p>
                          <p className="mt-1 text-xs text-muted-foreground">Detected {formatRelativeTime(gap.detected_at)}</p>
                        </div>
                        <Badge className="border-amber/20 bg-white text-amber">{gap.status.replaceAll("_", " ")}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Ranked candidate pool</CardTitle>
                <CardDescription>Deterministic backend ranking by role; scores are not recomputed in the browser.</CardDescription>
              </CardHeader>
              <CardContent>
                {data.ranked_candidates.length === 0 ? (
                  <EmptyState title="No candidates available" description="No eligible volunteer candidates were returned for the required roles." />
                ) : (
                  <div className="divide-y divide-border">
                    {data.ranked_candidates.map((candidate, index) => (
                      <div className="grid gap-2 py-3 sm:grid-cols-[32px_1fr_auto_auto] sm:items-center" key={`${candidate.role}-${candidate.volunteer.volunteer_id}`}>
                        <span className="grid size-7 place-items-center rounded-md bg-muted text-xs font-bold text-muted-foreground">{index + 1}</span>
                        <div>
                          <p className="text-sm font-semibold">{candidate.volunteer.display_name}</p>
                          <p className="text-xs text-muted-foreground">{candidate.needs_transport ? "Transport required" : "No transport dependency"}</p>
                        </div>
                        <Badge>{roleLabel(candidate.role)}</Badge>
                        <span className="text-right text-sm font-bold tabular-nums">{candidate.score.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-5">
              <Card className={data.needs_attention.length > 0 ? "border-red/20" : undefined}>
                <CardHeader>
                  <CardTitle className="text-base">Human decisions</CardTitle>
                  <CardDescription>Open RED interruptions related to this shift.</CardDescription>
                </CardHeader>
                <CardContent>
                  {data.needs_attention.length === 0 ? (
                    <EmptyState title="No review required" description="QUORUM has no unresolved human decision for this shift." />
                  ) : data.needs_attention.map((item) => (
                    <Link className="block rounded-xl border border-red/20 bg-red-soft/50 p-4 transition-colors hover:border-red/35 hover:bg-red-soft" href={`/human-decisions?decision=${encodeURIComponent(item.interrupt_id)}`} key={item.interrupt_id}>
                      <div className="flex items-center justify-between"><RouteBadge route={item.routing_class} /><span className="text-xs text-muted-foreground">{formatRelativeTime(item.created_at)}</span></div>
                      <p className="mt-3 text-sm font-semibold">{item.title}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.routing_reason ?? "Human review is required."}</p>
                      <span className="mt-3 inline-flex text-xs font-semibold text-red">Review decision →</span>
                    </Link>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Pending effects</CardTitle>
                  <CardDescription>Actions queued or settling for this operation.</CardDescription>
                </CardHeader>
                <CardContent>
                  {data.pending_effects.length === 0 ? (
                    <EmptyState title="Nothing pending" description="This shift has no queued or settling effects." />
                  ) : data.pending_effects.map((effect) => (
                    <Link className="flex items-start justify-between gap-3 border-b border-border py-3 transition-colors hover:bg-muted/40 last:border-b-0" href={`/pending-effects#${effect.pending_id}`} key={effect.pending_id}>
                      <div><p className="text-sm font-semibold">{effect.description}</p><p className="mt-1 text-xs text-muted-foreground">Settles {formatRelativeTime(effect.settle_at)}</p></div>
                      <PendingStatusBadge status={effect.status} />
                    </Link>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader className="flex-row items-start justify-between gap-4">
              <div><CardTitle className="text-base">Decision record</CardTitle><CardDescription className="mt-1">Recent ledger entries associated with this shift.</CardDescription></div>
              <Link className="text-xs font-semibold text-primary hover:underline" href={`/decision-feed?shift_id=${encodeURIComponent(shiftId)}`}>View full feed →</Link>
            </CardHeader>
            <CardContent>
              {data.recent_activity.length === 0 ? (
                <EmptyState title="No decisions recorded" description="Shift-specific agent decisions will appear here after processing." />
              ) : (
                <div className="divide-y divide-border">
                  {data.recent_activity.map((item) => (
                    <div className="grid gap-2 py-3 sm:grid-cols-[110px_1fr_auto] sm:items-center" key={item.entry_id}>
                      <RouteBadge route={item.routing_class} />
                      <div><p className="text-sm font-medium">{item.summary}</p><p className="mt-0.5 text-xs text-muted-foreground">{item.reason ?? "Recorded by QUORUM."}</p></div>
                      <span className="text-xs text-muted-foreground">{formatRelativeTime(item.timestamp)}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
