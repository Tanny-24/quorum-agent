import { Badge } from "@/components/ui/badge";
import type {
  InterruptStatus,
  PendingStatus,
  RoutingClass,
  ShiftOperationalStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { statusLabel } from "@/lib/format";

const routeStyles: Record<RoutingClass, string> = {
  GREEN: "border-green/20 bg-green-soft text-green",
  YELLOW: "border-amber/20 bg-amber-soft text-amber",
  RED: "border-red/20 bg-red-soft text-red",
  "SILENT/DEFER": "border-violet/20 bg-violet-soft text-violet",
};

const routeMeta: Record<RoutingClass, { icon: string; label: string }> = {
  GREEN: { icon: "✓", label: "GREEN" },
  YELLOW: { icon: "◷", label: "YELLOW" },
  RED: { icon: "!", label: "RED" },
  "SILENT/DEFER": { icon: "–", label: "SILENT / DEFER" },
};

const pendingMeta: Record<PendingStatus, { icon: string; style: string }> = {
  PENDING: { icon: "◷", style: "border-amber/20 bg-amber-soft text-amber" },
  SETTLING: { icon: "↻", style: "border-blue-200 bg-blue-50 text-blue-700" },
  SETTLED: { icon: "✓", style: "border-green/20 bg-green-soft text-green" },
  CANCELLED: { icon: "×", style: "border-slate-200 bg-slate-50 text-slate-600" },
  FAILED: { icon: "!", style: "border-red/20 bg-red-soft text-red" },
};

const decisionMeta: Record<InterruptStatus, { icon: string; style: string; label: string }> = {
  OPEN: { icon: "!", style: "border-red/20 bg-red-soft text-red", label: "Needs decision" },
  RESOLVING: { icon: "↻", style: "border-amber/20 bg-amber-soft text-amber", label: "Resolving" },
  RESOLVED: { icon: "✓", style: "border-green/20 bg-green-soft text-green", label: "Resolved" },
};

const shiftStyles: Record<ShiftOperationalStatus, string> = {
  SCHEDULED: "border-slate-200 bg-slate-50 text-slate-600",
  NEEDS_COVERAGE: "border-amber/20 bg-amber-soft text-amber",
  RECOVERING: "border-blue-200 bg-blue-50 text-blue-700",
  FULLY_STAFFED: "border-green/20 bg-green-soft text-green",
};

export function RouteBadge({ route }: { route: RoutingClass | null }) {
  if (!route) {
    return <Badge className="border-slate-200 bg-slate-50 text-slate-600">Recorded</Badge>;
  }
  const meta = routeMeta[route];
  return (
    <Badge className={routeStyles[route]}>
      <span className="mr-1" aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </Badge>
  );
}

export function ShiftStatusBadge({ status }: { status: ShiftOperationalStatus }) {
  return <Badge className={cn(shiftStyles[status])}>{statusLabel(status)}</Badge>;
}

export function PendingStatusBadge({ status }: { status: PendingStatus }) {
  const meta = pendingMeta[status];
  return (
    <Badge className={meta.style}>
      <span className="mr-1" aria-hidden="true">{meta.icon}</span>
      {status.charAt(0) + status.slice(1).toLowerCase()}
    </Badge>
  );
}

export function HumanDecisionStatusBadge({ status }: { status: InterruptStatus }) {
  const meta = decisionMeta[status];
  return (
    <Badge className={meta.style}>
      <span className="mr-1" aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </Badge>
  );
}
