import type {
  AttentionBudgetView,
  CancelPendingEffectResponse,
  DashboardSummary,
  DecisionFeedPage,
  DemoResetResponse,
  DemoScenarioView,
  HealthResponse,
  HumanDecisionDetail,
  HumanDecisionSummary,
  InterruptStatus,
  PendingEffectCompactView,
  PendingStatus,
  RecoveryRunDetail,
  ResolveInterruptRequest,
  ResolveInterruptResponse,
  RoutingClass,
  ShiftDetail,
  ShiftSummary,
  Role,
  RunDemoScenarioResponse,
  VolunteerDetailView,
  VolunteerOperationalStatus,
  VolunteerSummaryView,
} from "@/lib/types";

const API_PREFIX = "/api/quorum";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  signal?: AbortSignal;
  method?: "GET" | "POST";
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, {
      signal: options.signal,
      method: options.method ?? "GET",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("QUORUM API is unavailable.");
  }
  if (!response.ok) {
    let code: string | undefined;
    try {
      const payload = (await response.json()) as {
        detail?: string | { code?: string };
      };
      code = typeof payload.detail === "object" ? payload.detail.code : undefined;
    } catch {
      code = undefined;
    }
    throw new ApiError(
      response.status === 404
        ? "The requested QUORUM record was not found."
        : response.status === 409
          ? "This record changed before your action completed."
        : "QUORUM could not load this view.",
      response.status,
      code,
    );
  }
  return (await response.json()) as T;
}

export const getHealth = (signal?: AbortSignal) =>
  request<HealthResponse>("/health", { signal });

export const getDashboard = (signal?: AbortSignal) =>
  request<DashboardSummary>("/dashboard", { signal });

export const getShifts = (signal?: AbortSignal) =>
  request<ShiftSummary[]>("/shifts", { signal });

export const getShift = (shiftId: string, signal?: AbortSignal) =>
  request<ShiftDetail>(`/shifts/${encodeURIComponent(shiftId)}`, { signal });

export const getAttentionBudget = (signal?: AbortSignal) =>
  request<AttentionBudgetView>("/attention-budget", { signal });

export const getPendingEffects = (
  status?: PendingStatus,
  signal?: AbortSignal,
) =>
  request<PendingEffectCompactView[]>(
    status ? `/pending?status=${encodeURIComponent(status)}` : "/pending",
    { signal },
  );

export const getHumanDecisions = (
  status?: InterruptStatus,
  signal?: AbortSignal,
) =>
  request<HumanDecisionSummary[]>(
    status ? `/interrupts?status=${encodeURIComponent(status)}` : "/interrupts",
    { signal },
  );

export const getHumanDecision = (interruptId: string, signal?: AbortSignal) =>
  request<HumanDecisionDetail>(
    `/interrupts/${encodeURIComponent(interruptId)}`,
    { signal },
  );

export const resolveHumanDecision = (
  interruptId: string,
  command: ResolveInterruptRequest,
) =>
  request<ResolveInterruptResponse>(
    `/interrupts/${encodeURIComponent(interruptId)}/resolve`,
    { method: "POST", body: command },
  );

export const cancelPendingEffect = (pendingId: string) =>
  request<CancelPendingEffectResponse>(
    `/pending/${encodeURIComponent(pendingId)}/cancel`,
    {
      method: "POST",
      body: { actor: "demo-coordinator", expected_status: "PENDING" },
    },
  );

export interface DecisionFeedFilters {
  route?: RoutingClass;
  category?: string;
  shiftId?: string;
  cursor?: string;
  limit?: number;
}

export const getDecisionFeed = (
  filters: DecisionFeedFilters = {},
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams();
  if (filters.route) params.set("route", filters.route);
  if (filters.category) params.set("category", filters.category);
  if (filters.shiftId) params.set("shift_id", filters.shiftId);
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return request<DecisionFeedPage>(`/feed${query ? `?${query}` : ""}`, { signal });
};

export const getDemoScenarios = (signal?: AbortSignal) =>
  request<DemoScenarioView[]>("/demo/scenarios", { signal });

export const getDemoRuns = (signal?: AbortSignal) =>
  request<RecoveryRunDetail[]>("/demo/runs", { signal });

export const getDemoRun = (runId: string, signal?: AbortSignal) =>
  request<RecoveryRunDetail>(`/demo/runs/${encodeURIComponent(runId)}`, { signal });

export const runDemoScenario = (scenarioId: string, idempotencyKey: string) =>
  request<RunDemoScenarioResponse>(
    `/demo/scenarios/${encodeURIComponent(scenarioId)}/run`,
    {
      method: "POST",
      body: {
        idempotency_key: idempotencyKey,
        execution_mode: "deterministic_demo",
      },
    },
  );

export const resetDemo = () =>
  request<DemoResetResponse>("/demo/reset", { method: "POST" });

export interface VolunteerFilters {
  role?: Role;
  status?: VolunteerOperationalStatus;
  available?: boolean;
}

export const getVolunteers = (
  filters: VolunteerFilters = {},
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams();
  if (filters.role) params.set("role", filters.role);
  if (filters.status) params.set("status", filters.status);
  if (filters.available !== undefined) {
    params.set("available", String(filters.available));
  }
  const query = params.toString();
  return request<VolunteerSummaryView[]>(
    `/volunteers${query ? `?${query}` : ""}`,
    { signal },
  );
};

export const getVolunteer = (volunteerId: string, signal?: AbortSignal) =>
  request<VolunteerDetailView>(
    `/volunteers/${encodeURIComponent(volunteerId)}`,
    { signal },
  );
