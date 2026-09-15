"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getVolunteers } from "@/lib/api";
import { roleLabel } from "@/lib/format";
import type { Role, VolunteerOperationalStatus, VolunteerSummaryView } from "@/lib/types";

type RoleFilter = "ALL" | Role;
type StatusFilter = "ALL" | VolunteerOperationalStatus;
type AvailabilityFilter = "ALL" | "AVAILABLE";

function VolunteerStatus({ status }: { status: VolunteerOperationalStatus }) {
  return <Badge className={status === "ACTIVE" ? "border-green/20 bg-green-soft text-green" : "border-slate-200 bg-slate-50 text-slate-600"}><span className="mr-1" aria-hidden="true">{status === "ACTIVE" ? "✓" : "–"}</span>{status.charAt(0) + status.slice(1).toLowerCase()}</Badge>;
}

function Constraints({ volunteer }: { volunteer: VolunteerSummaryView }) {
  return volunteer.constraints.length > 0
    ? <span className="text-xs text-amber">{volunteer.constraints.join(" · ")}</span>
    : <span className="text-xs text-muted-foreground">No displayed constraints</span>;
}

export function VolunteersWorkspace() {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<RoleFilter>("ALL");
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [availability, setAvailability] = useState<AvailabilityFilter>("ALL");
  const loader = useCallback(
    (signal?: AbortSignal) => getVolunteers({
      role: role === "ALL" ? undefined : role,
      status: status === "ALL" ? undefined : status,
      available: availability === "AVAILABLE" ? true : undefined,
    }, signal),
    [availability, role, status],
  );
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 10_000);
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return query ? (data ?? []).filter((item) => item.display_name.toLowerCase().includes(query)) : data ?? [];
  }, [data, search]);

  return (
    <>
      <PageHeader eyebrow="Operations" title="Volunteers" description="Safe synthetic roster context for availability, roles, current assignments, and displayed coordination constraints." action={<Button variant="outline" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? "Refreshing…" : "Refresh roster"}</Button>} />
      <Card className="mb-5"><CardContent className="grid gap-3 pt-5 sm:grid-cols-2 xl:grid-cols-[minmax(240px,1fr)_180px_180px_180px]">
        <div><label className="mb-1.5 block text-xs font-semibold text-muted-foreground" htmlFor="volunteer-search">Search volunteer</label><Input id="volunteer-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Synthetic Volunteer 09" /></div>
        <div><label className="mb-1.5 block text-xs font-semibold text-muted-foreground" htmlFor="volunteer-role">Role</label><Select id="volunteer-role" value={role} onChange={(event) => setRole(event.target.value as RoleFilter)}><option value="ALL">All roles</option><option value="driver">Driver</option><option value="sorter">Sorter</option></Select></div>
        <div><label className="mb-1.5 block text-xs font-semibold text-muted-foreground" htmlFor="volunteer-status">Status</label><Select id="volunteer-status" value={status} onChange={(event) => setStatus(event.target.value as StatusFilter)}><option value="ALL">All statuses</option><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option></Select></div>
        <div><label className="mb-1.5 block text-xs font-semibold text-muted-foreground" htmlFor="volunteer-availability">Availability</label><Select id="volunteer-availability" value={availability} onChange={(event) => setAvailability(event.target.value as AvailabilityFilter)}><option value="ALL">Any availability</option><option value="AVAILABLE">Available shifts</option></Select></div>
      </CardContent></Card>

      {loading && !data ? (
        <div className="space-y-3" aria-label="Loading volunteers"><Skeleton className="h-20 rounded-xl" /><Skeleton className="h-20 rounded-xl" /><Skeleton className="h-20 rounded-xl" /></div>
      ) : !data ? (
        <ErrorState message={error ?? "Volunteers could not be loaded."} retry={() => void refresh()} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No volunteers match these filters." description="Adjust the search, role, status, or availability selection." />
      ) : (
        <>
          {error && <StaleNotice message={error} />}
          <p className="mb-3 text-xs font-medium text-muted-foreground">{filtered.length} synthetic volunteer{filtered.length === 1 ? "" : "s"}</p>
          <Card className="hidden md:block"><CardContent className="overflow-x-auto px-0 pb-0"><Table><TableHeader><TableRow className="hover:bg-transparent"><TableHead className="pl-5">Volunteer</TableHead><TableHead>Roles</TableHead><TableHead>Availability</TableHead><TableHead>Assignments</TableHead><TableHead>Status</TableHead><TableHead className="pr-5 text-right"><span className="sr-only">Open</span></TableHead></TableRow></TableHeader><TableBody>{filtered.map((volunteer) => <TableRow key={volunteer.volunteer_id}><TableCell className="min-w-56 pl-5"><p className="font-semibold">{volunteer.display_name}</p><div className="mt-1"><Constraints volunteer={volunteer} /></div></TableCell><TableCell><div className="flex flex-wrap gap-1">{volunteer.roles.map((item) => <Badge key={item}>{roleLabel(item)}</Badge>)}</div></TableCell><TableCell className="min-w-48"><p>{volunteer.availability_summary}</p></TableCell><TableCell className="font-semibold tabular-nums">{volunteer.current_assignment_count}</TableCell><TableCell><VolunteerStatus status={volunteer.status} /></TableCell><TableCell className="pr-5 text-right"><Link className="font-semibold text-primary hover:underline" href={`/volunteers/${volunteer.volunteer_id}`}>View profile</Link></TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
          <div className="grid gap-3 md:hidden">{filtered.map((volunteer) => <Link className="rounded-xl border border-border bg-white p-4 shadow-sm transition-colors hover:border-blue-200" href={`/volunteers/${volunteer.volunteer_id}`} key={volunteer.volunteer_id}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{volunteer.display_name}</p><p className="mt-1 text-xs text-muted-foreground">{volunteer.availability_summary}</p></div><VolunteerStatus status={volunteer.status} /></div><div className="mt-3 flex flex-wrap gap-2">{volunteer.roles.map((item) => <Badge key={item}>{roleLabel(item)}</Badge>)}<Badge>{volunteer.current_assignment_count} assignment{volunteer.current_assignment_count === 1 ? "" : "s"}</Badge></div><div className="mt-3"><Constraints volunteer={volunteer} /></div></Link>)}</div>
        </>
      )}
    </>
  );
}
