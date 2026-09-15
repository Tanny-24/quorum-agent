"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { RouteBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, StaleNotice } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import { getDecisionFeed } from "@/lib/api";
import { formatDateTime, formatRelativeTime } from "@/lib/format";
import type { DecisionFeedItem, DecisionFeedPage, RoutingClass } from "@/lib/types";

type RouteFilter = "ALL" | RoutingClass;

const routeFilters: { value: RouteFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "GREEN", label: "GREEN" },
  { value: "YELLOW", label: "YELLOW" },
  { value: "RED", label: "RED" },
  { value: "SILENT/DEFER", label: "SILENT" },
];

function FeedItem({ item }: { item: DecisionFeedItem }) {
  return (
    <article className="relative grid gap-3 border-b border-border py-5 last:border-b-0 md:grid-cols-[130px_minmax(0,1fr)_180px]">
      <div><RouteBadge route={item.route} /><p className="mt-2 text-xs text-muted-foreground">{item.category.replaceAll("_", " ")}</p></div>
      <div>
        <h2 className="font-semibold text-foreground">{item.title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.reason ? item.reason.replaceAll("_", " ") : "Recorded by QUORUM's deterministic decision ledger."}</p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs font-semibold">
          {item.shift_id && <Link className="text-primary hover:underline" href={`/shifts/${item.shift_id}`}>{item.shift_name ?? "Related shift"} →</Link>}
          {item.interrupt_id && <Link className="text-red hover:underline" href={`/human-decisions?decision=${encodeURIComponent(item.interrupt_id)}`}>Human decision →</Link>}
          {item.pending_id && <Link className="text-amber hover:underline" href={`/pending-effects#${item.pending_id}`}>Pending effect →</Link>}
        </div>
        {(item.attention_effect || (item.ev_score !== null && item.ev_threshold !== null)) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {item.attention_effect && <Badge className="border-violet/20 bg-violet-soft text-violet">{item.attention_effect === "SAFETY_OVERRIDE" ? "Attention safety override" : "Attention spent"}</Badge>}
            {item.ev_score !== null && item.ev_threshold !== null && <Badge>EV {item.ev_score.toFixed(2)} / threshold {item.ev_threshold.toFixed(2)}</Badge>}
          </div>
        )}
      </div>
      <div className="md:text-right">
        <time className="text-xs font-medium text-muted-foreground" dateTime={item.timestamp}>{formatDateTime(item.timestamp)}</time>
        <p className="mt-1 text-xs text-muted-foreground">{formatRelativeTime(item.timestamp)}</p>
        <p className="mt-3 font-mono text-[10px] text-slate-400" title={item.id}>{item.id.slice(0, 18)}</p>
      </div>
    </article>
  );
}

function FeedResults({ route, shiftId }: { route?: RoutingClass; shiftId?: string }) {
  const loader = useCallback(
    (signal?: AbortSignal) => getDecisionFeed({ route, shiftId, limit: 25 }, signal),
    [route, shiftId],
  );
  const { data, error, loading, refreshing, refresh } = usePolling(loader, 7_500);
  const [olderItems, setOlderItems] = useState<DecisionFeedItem[]>([]);
  const [olderPage, setOlderPage] = useState<DecisionFeedPage | null>(null);
  const [olderLoading, setOlderLoading] = useState(false);
  const [olderError, setOlderError] = useState<string | null>(null);
  const items = useMemo(() => {
    const unique = new Map<string, DecisionFeedItem>();
    [...(data?.items ?? []), ...olderItems].forEach((item) => unique.set(item.id, item));
    return [...unique.values()];
  }, [data, olderItems]);
  const nextCursor = olderPage ? olderPage.next_cursor : data?.next_cursor;
  const hasMore = olderPage ? olderPage.has_more : data?.has_more;

  const loadOlder = async () => {
    if (!nextCursor) return;
    setOlderLoading(true);
    setOlderError(null);
    try {
      const page = await getDecisionFeed({ route, shiftId, cursor: nextCursor, limit: 25 });
      setOlderItems((current) => [...current, ...page.items]);
      setOlderPage(page);
    } catch (loadError) {
      setOlderError(loadError instanceof Error ? loadError.message : "Older decisions could not be loaded.");
    } finally {
      setOlderLoading(false);
    }
  };

  if (loading && !data) {
    return <div className="space-y-3" aria-label="Loading decision feed"><Skeleton className="h-36 rounded-xl" /><Skeleton className="h-36 rounded-xl" /><Skeleton className="h-36 rounded-xl" /></div>;
  }
  if (!data) {
    return <ErrorState message={error ?? "Decision feed could not be loaded."} retry={() => void refresh()} />;
  }
  if (items.length === 0) {
    return <EmptyState title="No decisions have been recorded in this demo session." description="Change the route filter or process a synthetic operation to create ledger activity." />;
  }

  return (
    <>
      {error && <StaleNotice message={error} />}
      <Card>
        <CardContent className="px-5 pb-0">{items.map((item) => <FeedItem item={item} key={item.id} />)}</CardContent>
      </Card>
      <div className="mt-4 flex flex-col items-center gap-2">
        {hasMore && <Button variant="outline" disabled={olderLoading || refreshing} onClick={() => void loadOlder()}>{olderLoading ? "Loading older…" : "Load older decisions"}</Button>}
        {olderError && <p className="text-sm text-red" role="status">{olderError}</p>}
      </div>
    </>
  );
}

export function DecisionFeedWorkspace({ initialShiftId }: { initialShiftId?: string }) {
  const [route, setRoute] = useState<RouteFilter>("ALL");
  const [shiftId, setShiftId] = useState(initialShiftId);

  return (
    <>
      <PageHeader eyebrow="Observability" title="Decision Feed" description="A chronological, sanitized record of what QUORUM decided, why it decided it, and which operational context it affected." />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" aria-label="Filter decision feed by route">
          {routeFilters.map((item) => <Button key={item.value} size="sm" variant={route === item.value ? "default" : "outline"} aria-pressed={route === item.value} onClick={() => setRoute(item.value)}>{item.label}</Button>)}
        </div>
        {shiftId && <Badge className="border-blue-200 bg-blue-50 text-blue-700">Shift filter active <button className="ml-2 font-bold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setShiftId(undefined)} aria-label="Clear shift filter">×</button></Badge>}
      </div>
      <FeedResults key={`${route}:${shiftId ?? "all"}`} route={route === "ALL" ? undefined : route} shiftId={shiftId} />
    </>
  );
}
