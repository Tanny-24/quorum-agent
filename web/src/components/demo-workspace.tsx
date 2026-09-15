"use client";

import Link from "next/link";
import { useState } from "react";

import { ConfirmationDialog } from "@/components/confirmation-dialog";
import { PageHeader } from "@/components/page-header";
import { RouteBadge, ShiftStatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/view-state";
import { usePolling } from "@/hooks/use-polling";
import {
  getDashboard,
  getDecisionFeed,
  getDemoScenarios,
  getHumanDecisions,
  getPendingEffects,
  getShifts,
  resetDemo,
  runDemoScenario,
} from "@/lib/api";
import { formatDateTime, roleLabel } from "@/lib/format";
import type { DemoScenarioView, RecoveryRunDetail, RecoveryStepStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type Confirmation =
  | { type: "run"; scenario: DemoScenarioView }
  | { type: "reset" };

const stepMeta: Record<RecoveryStepStatus, { icon: string; className: string }> = {
  COMPLETED: { icon: "✓", className: "border-green/20 bg-green-soft text-green" },
  WAITING_FOR_HUMAN: { icon: "!", className: "border-red/20 bg-red-soft text-red" },
  FAILED: { icon: "×", className: "border-red/20 bg-red-soft text-red" },
};

function ScenarioCard({
  scenario,
  busy,
  onRun,
}: {
  scenario: DemoScenarioView;
  busy: boolean;
  onRun: () => void;
}) {
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <div className={cn("h-1", scenario.expected_route === "GREEN" ? "bg-green" : scenario.expected_route === "YELLOW" ? "bg-amber" : "bg-red")} />
      <CardHeader className="flex-1">
        <div className="flex items-center justify-between gap-3">
          <Badge className="border-blue-200 bg-blue-50 text-primary">{scenario.id.slice(-1).toUpperCase()}</Badge>
          <div className="flex items-center gap-2"><span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">Expected path</span><RouteBadge route={scenario.expected_route} /></div>
        </div>
        <CardTitle className="pt-3 text-lg">{scenario.title}</CardTitle>
        <CardDescription className="leading-6">{scenario.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-xs font-medium text-muted-foreground">{scenario.expected_human_involvement}</p>
        <Button className="w-full" disabled={busy} onClick={onRun}>Run Scenario {scenario.id.slice(-1).toUpperCase()}</Button>
      </CardContent>
    </Card>
  );
}

function RunTimeline({ run }: { run: RecoveryRunDetail }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><CardTitle className="text-base">Actual workflow timeline</CardTitle><CardDescription className="mt-1">Only backend-confirmed deterministic steps are shown.</CardDescription></div>
          <Badge className={run.status === "COMPLETED" ? "border-green/20 bg-green-soft text-green" : run.status === "WAITING_FOR_HUMAN" ? "border-red/20 bg-red-soft text-red" : "border-amber/20 bg-amber-soft text-amber"}>{run.status.replaceAll("_", " ")}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <ol className="space-y-0">
          {run.steps.map((step, index) => {
            const meta = stepMeta[step.status];
            return (
              <li className="relative grid grid-cols-[36px_minmax(0,1fr)] gap-3 pb-5 last:pb-0" key={step.step_id}>
                {index < run.steps.length - 1 && <span className="absolute bottom-0 left-[17px] top-9 w-px bg-border" aria-hidden="true" />}
                <span className={cn("z-10 grid size-9 place-items-center rounded-full border text-sm font-bold", meta.className)} aria-hidden="true">{meta.icon}</span>
                <div className="pt-1"><p className="text-sm font-semibold text-foreground">{step.label}</p><p className="mt-1 text-sm leading-6 text-muted-foreground">{step.summary}</p></div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}

function RunOutcome({ run }: { run: RecoveryRunDetail }) {
  return (
    <Card className={run.status === "FAILED" ? "border-red/20" : run.status === "WAITING_FOR_HUMAN" ? "border-red/20" : "border-green/20"}>
      <CardHeader><CardTitle className="text-base">Outcome</CardTitle><CardDescription>{run.outcome ?? "No outcome was returned."}</CardDescription></CardHeader>
      <CardContent className="space-y-5">
        {run.error && <div className="rounded-lg border border-red/20 bg-red-soft px-4 py-3 text-sm text-red">{run.error}</div>}
        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl bg-muted p-4"><dt className="text-xs text-muted-foreground">Human decision</dt><dd className="mt-1 font-semibold">{run.human_decision_required ? "Required" : "Not required"}</dd></div>
          <div className="rounded-xl bg-muted p-4"><dt className="text-xs text-muted-foreground">Attention Budget</dt><dd className="mt-1 font-semibold">{run.attention_budget_delta === 0 ? "No change" : `+${run.attention_budget_delta} spent`}</dd></div>
          <div className="rounded-xl bg-muted p-4"><dt className="text-xs text-muted-foreground">Completed</dt><dd className="mt-1 text-sm font-semibold">{run.completed_at ? formatDateTime(run.completed_at) : "Still running"}</dd></div>
        </dl>
        {run.final_shift && (
          <div className="rounded-xl border border-border p-4">
            <div className="flex flex-wrap items-center justify-between gap-3"><p className="font-semibold">{run.final_shift.site_name}</p><ShiftStatusBadge status={run.final_shift.status} /></div>
            <div className="mt-3 flex flex-wrap gap-2">{run.final_shift.coverage.map((item) => <Badge key={item.role}>{roleLabel(item.role)} {item.assigned}/{item.required}</Badge>)}</div>
          </div>
        )}
        <div className="flex flex-wrap gap-4 text-sm font-semibold">
          <Link className="text-primary hover:underline" href={`/shifts/${run.shift_id}`}>View Shift →</Link>
          <Link className="text-primary hover:underline" href={`/decision-feed?shift_id=${encodeURIComponent(run.shift_id)}`}>View Decision Feed →</Link>
          {run.interrupt_id && <Link className="text-red hover:underline" href={`/human-decisions?decision=${encodeURIComponent(run.interrupt_id)}`}>View Human Decision →</Link>}
        </div>
      </CardContent>
    </Card>
  );
}

export function DemoWorkspace() {
  const { data: scenarios, error, loading, refresh } = usePolling(getDemoScenarios, null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [run, setRun] = useState<RecoveryRunDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [retryCommand, setRetryCommand] = useState<{ scenarioId: string; key: string } | null>(null);

  const execute = async () => {
    if (!confirmation) return;
    setBusy(true);
    setMessage(null);
    if (confirmation.type === "reset") {
      try {
        const result = await resetDemo();
        setRun(null);
        setRetryCommand(null);
        setConfirmation(null);
        try {
          await Promise.all([getDashboard(), getShifts(), getHumanDecisions(), getPendingEffects(), getDecisionFeed()]);
          setMessage(`Synthetic workspace restored: ${result.shifts_restored} shifts and ${result.volunteers_restored} volunteers.`);
        } catch {
          setMessage("The backend confirmed the synthetic reset, but one follow-up product view could not be refreshed.");
        }
      } catch (resetError) {
        setMessage(resetError instanceof Error ? resetError.message : "Demo reset failed. Existing state was preserved.");
      } finally {
        setBusy(false);
      }
      return;
    }

    const scenario = confirmation.scenario;
    const command = retryCommand?.scenarioId === scenario.id
      ? retryCommand
      : { scenarioId: scenario.id, key: `demo:${scenario.id}:${crypto.randomUUID()}` };
    setRetryCommand(command);
    try {
      const result = await runDemoScenario(scenario.id, command.key);
      setRun(result.run);
      setRetryCommand(null);
      setConfirmation(null);
      setMessage(
        result.duplicate
          ? "The existing idempotent run was returned."
          : result.run.status === "FAILED"
            ? "The backend returned a failed workflow. Review the safe failure summary below."
            : "The backend completed the deterministic scenario run.",
      );
    } catch (runError) {
      setConfirmation(null);
      setMessage(runError instanceof Error ? runError.message : "The scenario could not be run. No successful outcome was assumed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader eyebrow="Controlled simulation" title="Synthetic Demo" description="Runs use synthetic data and QUORUM’s real deterministic coordination services. No real volunteers are contacted." action={<div className="flex flex-wrap items-center gap-2"><Badge className="border-violet/20 bg-violet-soft text-violet">Deterministic Demo</Badge><Button variant="outline" disabled={busy} onClick={() => setConfirmation({ type: "reset" })}>Reset Demo</Button></div>} />
      {message && <div className="mb-5 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800" role="status" aria-live="polite">{message}</div>}
      {loading && !scenarios ? (
        <div className="grid gap-4 lg:grid-cols-3" aria-label="Loading demo scenarios"><Skeleton className="h-72 rounded-xl" /><Skeleton className="h-72 rounded-xl" /><Skeleton className="h-72 rounded-xl" /></div>
      ) : !scenarios ? (
        <ErrorState message={error ?? "Demo scenarios could not be loaded."} retry={() => void refresh()} />
      ) : scenarios.length === 0 ? (
        <EmptyState title="No synthetic scenarios are available." description="The backend did not return a demo catalog." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">{scenarios.map((scenario) => <ScenarioCard scenario={scenario} busy={busy} onRun={() => setConfirmation({ type: "run", scenario })} key={scenario.id} />)}</div>
      )}
      {run && <div className="mt-6 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]"><RunTimeline run={run} /><RunOutcome run={run} /></div>}
      <ConfirmationDialog open={confirmation !== null} title={confirmation?.type === "reset" ? "Reset the synthetic demo?" : `Run ${confirmation?.type === "run" ? confirmation.scenario.title : "scenario"}?`} description={confirmation?.type === "reset" ? "This restores the synthetic Riverside demo workspace and clears its runs, gaps, assignments, decisions, pending effects, budget, and feed." : "This changes only the local synthetic workspace using deterministic services. No Gemini request or real volunteer contact will occur."} confirmLabel={confirmation?.type === "reset" ? "Confirm reset" : "Run scenario"} destructive={confirmation?.type === "reset"} busy={busy} onOpenChange={(open) => { if (!open && !busy) setConfirmation(null); }} onConfirm={() => void execute()} />
    </>
  );
}
