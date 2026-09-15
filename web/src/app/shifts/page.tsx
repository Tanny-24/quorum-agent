"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { ShiftStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getShifts } from "@/lib/api";
import { formatDateTime, formatTime, roleLabel } from "@/lib/format";
import type { ShiftSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "needs_coverage" | "fully_staffed";

const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "needs_coverage", label: "Needs coverage" },
  { value: "fully_staffed", label: "Fully staffed" },
];

function filterShift(shift: ShiftSummary, filter: Filter) {
  if (filter === "needs_coverage") {
    return shift.status === "NEEDS_COVERAGE" || shift.status === "RECOVERING";
  }
  if (filter === "fully_staffed") return shift.status === "FULLY_STAFFED";
  return true;
}

function ShiftsSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading shifts">
      {Array.from({ length: 4 }).map((_, index) => (
        <Skeleton className="h-20 rounded-xl" key={index} />
      ))}
    </div>
  );
}

export default function ShiftsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const { data, error, loading, refreshing, refresh } = usePolling(getShifts, null);
  const filtered = useMemo(
    () => (data ?? []).filter((shift) => filterShift(shift, filter)),
    [data, filter],
  );

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="Shifts"
        description="Backend-derived staffing coverage, open role gaps, and recovery status for every scheduled operation."
        action={
          <Button variant="outline" onClick={() => void refresh()} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh shifts"}
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2" aria-label="Filter shifts">
        {filters.map((item) => (
          <Button
            key={item.value}
            size="sm"
            variant={filter === item.value ? "default" : "outline"}
            onClick={() => setFilter(item.value)}
            aria-pressed={filter === item.value}
          >
            {item.label}
            {data && (
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px] tabular-nums",
                  filter === item.value ? "bg-white/15" : "bg-muted",
                )}
              >
                {data.filter((shift) => filterShift(shift, item.value)).length}
              </span>
            )}
          </Button>
        ))}
      </div>

      {loading && !data ? (
        <ShiftsSkeleton />
      ) : !data ? (
        <ErrorState message={error ?? "No shift state was returned."} retry={() => void refresh()} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={data.length === 0 ? "No shifts scheduled" : "No shifts match this filter"}
          description={
            data.length === 0
              ? "Shifts will appear here after they are added to the QUORUM runtime."
              : "Choose another status to see the remaining operations."
          }
        />
      ) : (
        <Card>
          <CardContent className="overflow-x-auto px-0 pb-0">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="pl-5">Site &amp; time</TableHead>
                  <TableHead>Coverage</TableHead>
                  <TableHead>Open gaps</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="pr-5 text-right"><span className="sr-only">Open</span></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((shift) => (
                  <TableRow key={shift.shift_id}>
                    <TableCell className="min-w-56 pl-5">
                      <p className="font-semibold text-foreground">{shift.site_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatDateTime(shift.starts_at)}–{formatTime(shift.ends_at)}
                      </p>
                    </TableCell>
                    <TableCell className="min-w-52">
                      <div className="flex flex-wrap gap-2">
                        {shift.coverage.map((coverage) => (
                          <span className="rounded-md bg-muted px-2 py-1 text-xs" key={coverage.role}>
                            {roleLabel(coverage.role)} {coverage.assigned}/{coverage.required}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={cn("font-semibold tabular-nums", shift.gap_count > 0 && "text-amber")}>
                        {shift.gap_count}
                      </span>
                    </TableCell>
                    <TableCell><ShiftStatusBadge status={shift.status} /></TableCell>
                    <TableCell className="pr-5 text-right">
                      <Link className="text-sm font-semibold text-primary hover:underline" href={`/shifts/${shift.shift_id}`}>
                        View shift
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
