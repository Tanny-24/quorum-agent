"use client";

import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { RouteBadge, ShiftStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getDashboard } from "@/lib/api";
import { formatDateTime, formatRelativeTime, roleLabel } from "@/lib/format";

function OverviewSkeleton() {
  return (
    <div className="space-y-5" aria-label="Loading overview">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton className="h-36 rounded-xl" key={index} />
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.85fr]">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    </div>
  );
}

function MetricCard({ label, value, note, href }: { label: string; value: number; note: string; href?: string }) {
  const card = (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <div className="text-3xl font-bold tracking-tight text-navy tabular-nums">{value}</div>
      </CardHeader>
      <CardContent>
        <p className="text-xs leading-5 text-muted-foreground">{note}</p>
      </CardContent>
    </Card>
  );
  return href ? (
    <Link className="rounded-xl transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={href}>
      {card}
    </Link>
  ) : card;
}

export default function OverviewPage() {
  const { data, error, loading, refreshing, refresh } = usePolling(
    getDashboard,
    10_000,
  );

  return (
    <>
      <PageHeader
        eyebrow="Operations overview"
        title="Good morning, coordinator"
        description="See what QUORUM is handling, what is waiting to settle, and where human judgment is genuinely required."
        action={
          <div className="flex flex-wrap gap-2">
            <Link className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2" href="/demo">Run Demo</Link>
            <Button variant="outline" onClick={() => void refresh()} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh state"}
            </Button>
          </div>
        }
      />

      {loading && !data ? (
        <OverviewSkeleton />
      ) : !data ? (
        <ErrorState message={error ?? "No dashboard state was returned."} retry={() => void refresh()} />
      ) : (
        <div>
          {error && <StaleNotice message={error} />}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Card className="border-blue-100 bg-[linear-gradient(145deg,#ffffff_0%,#f4f7ff_100%)] sm:col-span-2 xl:col-span-1">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardDescription>Attention Budget</CardDescription>
                  <span className="rounded-md bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-primary">
                    Runtime
                  </span>
                </div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-bold tracking-tight text-navy tabular-nums">
                    {data.attention_budget.spent}
                  </span>
                  <span className="text-sm font-medium text-muted-foreground">
                    of {data.attention_budget.allowance} used
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <Progress
                  value={data.attention_budget.spent}
                  max={data.attention_budget.allowance}
                  label="Attention Budget used"
                />
                <p className="mt-3 text-xs text-muted-foreground">
                  {data.attention_budget.remaining} interruptions remain
                  {data.attention_budget.overrides > 0
                    ? ` · ${data.attention_budget.overrides} safety override`
                    : ""}
                </p>
              </CardContent>
            </Card>
            <MetricCard
              label="Open staffing gaps"
              value={data.counts.open_gaps}
              note="Detected role-level gaps"
            />
            <MetricCard
              label="Active recoveries"
              value={data.counts.active_recoveries}
              note="Backend lifecycle in progress"
            />
            <MetricCard
              label="Pending effects"
              value={data.counts.pending_effects}
              note="Queued or settling actions"
              href="/pending-effects"
            />
            <MetricCard
              label="Human decisions"
              value={data.counts.human_decisions_required}
              note="Open RED interruptions"
              href="/human-decisions"
            />
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_0.85fr]">
            <Card>
              <CardHeader className="flex-row items-start justify-between">
                <div>
                  <CardTitle className="text-base">Active operations</CardTitle>
                  <CardDescription className="mt-1">
                    Shifts with detected gaps or recovery state.
                  </CardDescription>
                </div>
                <Link href="/shifts" className="text-xs font-semibold text-primary hover:underline">
                  View all shifts
                </Link>
              </CardHeader>
              <CardContent>
                {data.active_operations.length === 0 ? (
                  <EmptyState
                    title="Operations are clear"
                    description="No detected staffing gaps or active recovery work need monitoring."
                  />
                ) : (
                  <div className="space-y-3">
                    {data.active_operations.map((shift) => (
                      <Link
                        key={shift.shift_id}
                        href={`/shifts/${shift.shift_id}`}
                        className="flex flex-col gap-3 rounded-xl border border-border px-4 py-4 transition-colors hover:border-blue-200 hover:bg-blue-50/30 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-foreground">{shift.site_name}</p>
                            <ShiftStatusBadge status={shift.status} />
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {formatDateTime(shift.starts_at)} · {shift.gap_count} open gap
                            {shift.gap_count === 1 ? "" : "s"}
                          </p>
                        </div>
                        <div className="flex gap-2 text-xs text-muted-foreground">
                          {shift.coverage.map((coverage) => (
                            <span className="rounded-md bg-muted px-2 py-1" key={coverage.role}>
                              {roleLabel(coverage.role)} {coverage.assigned}/{coverage.required}
                            </span>
                          ))}
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className={data.needs_attention.length > 0 ? "border-red/20" : undefined}>
              <CardHeader>
                <CardTitle className="text-base">Needs your attention</CardTitle>
                <CardDescription>Layer-0 and consequential RED decisions.</CardDescription>
              </CardHeader>
              <CardContent>
                {data.needs_attention.length === 0 ? (
                  <EmptyState
                    title="No human decisions required"
                    description="QUORUM has not encountered a case that requires your judgment."
                  />
                ) : (
                  <div className="space-y-3">
                    {data.needs_attention.map((item) => (
                      <Link className="block rounded-xl border border-red/15 bg-red-soft/50 p-4 transition-colors hover:border-red/30 hover:bg-red-soft" href={`/human-decisions?decision=${encodeURIComponent(item.interrupt_id)}`} key={item.interrupt_id}>
                        <div className="flex items-center justify-between gap-3">
                          <RouteBadge route="RED" />
                          <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(item.created_at)}
                          </span>
                        </div>
                        <p className="mt-3 text-sm font-semibold text-foreground">{item.title}</p>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                          {item.routing_reason ?? "Human review required before proceeding."}
                        </p>
                        <span className="mt-3 inline-flex text-xs font-semibold text-red">Review decision →</span>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-5">
            <CardHeader className="flex-row items-start justify-between">
              <div>
                <CardTitle className="text-base">Recent agent activity</CardTitle>
                <CardDescription className="mt-1">
                  Backend-recorded decisions—not generated narrative.
                </CardDescription>
              </div>
              <div className="text-right">
                <Link className="block text-xs font-semibold text-primary hover:underline" href="/decision-feed">Open decision feed →</Link>
                <span className="mt-1 block text-xs text-muted-foreground">Updated {formatRelativeTime(data.generated_at)}</span>
              </div>
            </CardHeader>
            <CardContent>
              {data.recent_activity.length === 0 ? (
                <EmptyState
                  title="No recent agent activity"
                  description="Decision records will appear here when events are processed."
                />
              ) : (
                <div className="divide-y divide-border">
                  {data.recent_activity.map((item) => (
                    <div className="grid gap-2 py-3 sm:grid-cols-[110px_1fr_auto] sm:items-center" key={item.entry_id}>
                      <RouteBadge route={item.routing_class} />
                      <div>
                        <p className="text-sm font-medium text-foreground">{item.summary}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {item.reason ?? "Recorded by the deterministic decision ledger."}
                        </p>
                      </div>
                      <time className="text-xs text-muted-foreground" dateTime={item.timestamp}>
                        {formatRelativeTime(item.timestamp)}
                      </time>
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
