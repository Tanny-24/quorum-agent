"use client";

import { getHealth } from "@/lib/api";
import { usePolling } from "@/hooks/use-polling";

export function BackendStatus() {
  const { data, loading } = usePolling(getHealth, 15_000);
  const online = data?.status === "ok";
  return (
    <div
      className="flex items-center gap-2 text-xs font-medium text-muted-foreground"
      aria-live="polite"
    >
      <span
        className={`size-2 rounded-full ${
          loading ? "bg-slate-300" : online ? "bg-green" : "bg-red"
        }`}
      />
      {loading ? "Checking API" : online ? "Backend connected" : "Backend offline"}
    </div>
  );
}
