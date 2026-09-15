"use client";

import Link from "next/link";
import { useCallback } from "react";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { RouteBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getVolunteer } from "@/lib/api";
import { formatDateTime, formatRelativeTime, roleLabel } from "@/lib/format";

export function VolunteerDetailWorkspace() {
  const params = useParams<{ id: string }>();
  const volunteerId = params.id;
  const loader = useCallback((signal?: AbortSignal) => getVolunteer(volunteerId, signal), [volunteerId]);
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 10_000);

  return (
    <>
      <Link className="mb-4 inline-flex text-sm font-semibold text-primary hover:underline" href="/volunteers">← Back to volunteers</Link>
      <PageHeader eyebrow="Volunteer profile" title={data?.display_name ?? "Synthetic volunteer"} description="Safe operational context only; private personnel and provider data are not exposed." action={<Button variant="outline" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "Refresh profile"}</Button>} />
      {loading && !data ? (
        <div className="grid gap-5 lg:grid-cols-2"><Skeleton className="h-64 rounded-xl" /><Skeleton className="h-64 rounded-xl" /></div>
      ) : !data ? (
        <ErrorState message={error ?? "Volunteer could not be loaded."} retry={() => void refresh()} />
      ) : (
        <div className="space-y-5">
          {error && <StaleNotice message={error} />}
          <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
            <Card><CardHeader><div className="flex items-center justify-between gap-3"><CardTitle className="text-base">Profile summary</CardTitle><Badge className={data.status === "ACTIVE" ? "border-green/20 bg-green-soft text-green" : "border-slate-200 bg-slate-50 text-slate-600"}>{data.status === "ACTIVE" ? "✓ Active" : "– Inactive"}</Badge></div><CardDescription>Synthetic coordinator-facing information.</CardDescription></CardHeader><CardContent className="space-y-5"><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Eligible roles</p><div className="mt-2 flex flex-wrap gap-2">{data.roles.map((role) => <Badge key={role}>{roleLabel(role)}</Badge>)}</div></div><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Availability</p><p className="mt-2 text-sm font-medium">{data.availability_summary}</p></div><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Safe constraints</p><p className="mt-2 text-sm font-medium">{data.constraints.length ? data.constraints.join(" · ") : "No displayed operational constraints"}</p></div><div><p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Contact load</p><p className="mt-2 text-sm font-medium">{data.contact_load_summary}</p><p className="mt-1 text-xs text-muted-foreground">Historical contact counters are not presented as maintained product data yet.</p></div></CardContent></Card>
            <Card><CardHeader><CardTitle className="text-base">Current assignments</CardTitle><CardDescription>Capacity-guarded assignments confirmed by the backend.</CardDescription></CardHeader><CardContent>{data.assignments.length === 0 ? <EmptyState title="No current assignments" description="Assignments created by deterministic demo runs will appear here." /> : <div className="divide-y divide-border">{data.assignments.map((assignment) => <Link className="flex flex-col gap-2 py-4 transition-colors hover:bg-muted/40 sm:flex-row sm:items-center sm:justify-between" href={`/shifts/${assignment.shift.shift_id}`} key={assignment.assignment_id}><div><p className="font-semibold">{assignment.shift.site_name}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(assignment.shift.starts_at)} · confirmed {formatRelativeTime(assignment.confirmed_at)}</p></div><Badge>{roleLabel(assignment.role)}</Badge></Link>)}</div>}</CardContent></Card>
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <Card><CardHeader><CardTitle className="text-base">Available shifts</CardTitle><CardDescription>Availability declared in the synthetic roster.</CardDescription></CardHeader><CardContent>{data.available_shifts.length === 0 ? <EmptyState title="No available shifts" description="This volunteer has no current synthetic availability." /> : <div className="divide-y divide-border">{data.available_shifts.map((shift) => <Link className="flex items-center justify-between gap-3 py-3 text-sm hover:bg-muted/40" href={`/shifts/${shift.shift_id}`} key={shift.shift_id}><div><p className="font-semibold">{shift.site_name}</p><p className="mt-1 text-xs text-muted-foreground">{formatDateTime(shift.starts_at)}</p></div><span className="font-semibold text-primary">View →</span></Link>)}</div>}</CardContent></Card>
            <Card><CardHeader><CardTitle className="text-base">Recent coordination activity</CardTitle><CardDescription>Sanitized Decision Ledger records related to this volunteer.</CardDescription></CardHeader><CardContent>{data.recent_activity.length === 0 ? <EmptyState title="No related activity" description="No audited coordination records are associated with this volunteer yet." /> : <div className="divide-y divide-border">{data.recent_activity.map((item) => <div className="grid gap-2 py-3 sm:grid-cols-[110px_minmax(0,1fr)_auto] sm:items-center" key={item.id}><RouteBadge route={item.route} /><div><p className="text-sm font-medium">{item.title}</p><p className="mt-0.5 text-xs text-muted-foreground">{item.reason ?? "Recorded by QUORUM."}</p></div><span className="text-xs text-muted-foreground">{formatRelativeTime(item.timestamp)}</span></div>)}</div>}</CardContent></Card>
          </div>
        </div>
      )}
    </>
  );
}
