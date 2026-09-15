export type Role = "driver" | "sorter";
export type RoutingClass = "GREEN" | "YELLOW" | "RED" | "SILENT/DEFER";
export type GapStatus =
  | "DETECTED"
  | "ANALYZING"
  | "SEARCHING"
  | "CONTACTING"
  | "AWAITING"
  | "ESCALATION_REQUIRED"
  | "WAITING_FOR_HUMAN"
  | "RESUMING"
  | "DEFERRED"
  | "RESOLVED"
  | "FAILED";
export type ShiftOperationalStatus =
  | "SCHEDULED"
  | "NEEDS_COVERAGE"
  | "RECOVERING"
  | "FULLY_STAFFED";
export type PendingStatus =
  | "PENDING"
  | "SETTLING"
  | "SETTLED"
  | "CANCELLED"
  | "FAILED";
export type InterruptStatus = "OPEN" | "RESOLVING" | "RESOLVED";
export type HumanDecisionAction = "APPROVE" | "VETO";
export type RecoveryRunStatus =
  | "RUNNING"
  | "COMPLETED"
  | "WAITING_FOR_HUMAN"
  | "FAILED";
export type RecoveryStepStatus = "COMPLETED" | "WAITING_FOR_HUMAN" | "FAILED";
export type VolunteerOperationalStatus = "ACTIVE" | "INACTIVE";

export interface HealthResponse {
  status: "ok";
}

export interface AttentionBudgetView {
  allowance: number;
  spent: number;
  remaining: number;
  overrides: number;
}

export interface DashboardCounts {
  total_shifts: number;
  open_gaps: number;
  active_recoveries: number;
  pending_effects: number;
  human_decisions_required: number;
}

export interface RoleCoverage {
  role: Role;
  required: number;
  assigned: number;
  shortfall: number;
}

export interface GapSummary {
  gap_id: string;
  role: Role;
  shortfall: number;
  status: GapStatus;
  detected_at: string;
}

export interface VolunteerCompactView {
  volunteer_id: string;
  display_name: string;
}

export interface RelatedShiftView {
  shift_id: string;
  site_id: string;
  site_name: string;
  starts_at: string;
  ends_at: string;
}

export interface RelatedNegotiationView {
  thread_id: string;
  status: "OPEN" | "AWAITING_REPLY" | "ACCEPTED" | "DECLINED" | "ESCALATED" | "TIMED_OUT";
}

export interface HumanDecisionEvidence {
  label: string;
  value: string;
}

export interface AssignmentView {
  assignment_id: string;
  volunteer: VolunteerCompactView;
  role: Role;
  confirmed_at: string;
}

export interface RankedCandidateView {
  volunteer: VolunteerCompactView;
  role: Role;
  score: number;
  breakdown: Record<string, number>;
  needs_transport: boolean;
}

export interface InterruptCompactView {
  interrupt_id: string;
  status: InterruptStatus;
  title: string;
  created_at: string;
  routing_class: RoutingClass;
  safety_reason: string | null;
  routing_reason: string | null;
  shift_id: string | null;
  volunteer_id: string | null;
  attention_spent: boolean;
  attention_override: boolean;
}

export interface HumanDecisionResolution {
  action: HumanDecisionAction;
  note: string | null;
  actor: string;
  outcome: string;
  automatic_continuation: boolean;
  resolved_at: string;
}

export interface HumanDecisionSummary {
  interrupt_id: string;
  status: InterruptStatus;
  title: string;
  reason: string;
  route: RoutingClass;
  created_at: string;
  resolved_at: string | null;
  safety_reason: string | null;
  routing_reason: string | null;
  shift: RelatedShiftView | null;
  volunteer: VolunteerCompactView | null;
  attention_spent: boolean;
  attention_override: boolean;
  allowed_actions: HumanDecisionAction[];
  version: number;
}

export interface HumanDecisionDetail extends HumanDecisionSummary {
  negotiation: RelatedNegotiationView | null;
  evidence: HumanDecisionEvidence[];
  resolution: HumanDecisionResolution | null;
}

export interface ResolveInterruptRequest {
  action: HumanDecisionAction;
  note: string | null;
  actor: "demo-coordinator";
  expected_version: number;
}

export interface ResolveInterruptResponse {
  resolved: boolean;
  outcome: string;
  automatic_continuation: boolean;
  decision: HumanDecisionDetail;
}

export interface PendingEffectCompactView {
  effect_id: string;
  pending_id: string;
  effect_type: string;
  description: string;
  status: PendingStatus;
  created_at: string;
  settle_at: string;
  updated_at: string;
  settled_at: string | null;
  can_cancel: boolean;
  cancellable: boolean;
  shift_id: string | null;
  volunteer_id: string | null;
  thread_id: string | null;
  related_shift: RelatedShiftView | null;
  result_summary: string | null;
  failure_summary: string | null;
}

export interface CancelPendingEffectResponse {
  cancelled: boolean;
  reason: string;
}

export interface DecisionFeedItem {
  id: string;
  entry_id: string;
  timestamp: string;
  category: string;
  decision: string;
  summary: string;
  title: string;
  route: RoutingClass | null;
  routing_class: RoutingClass | null;
  reason: string | null;
  event_id: string | null;
  gap_id: string | null;
  shift_id: string | null;
  shift_name: string | null;
  interrupt_id: string | null;
  pending_id: string | null;
  attention_effect: "SPENT" | "SAFETY_OVERRIDE" | null;
  ev_score: number | null;
  ev_threshold: number | null;
}

export interface DecisionFeedPage {
  items: DecisionFeedItem[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface DemoScenarioView {
  id: string;
  title: string;
  description: string;
  expected_route: RoutingClass;
  expected_human_involvement: string;
  execution_mode: "deterministic_demo";
}

export interface RecoveryRunStepView {
  step_id: string;
  step_type: string;
  label: string;
  status: RecoveryStepStatus;
  timestamp: string;
  related_entity_id: string | null;
  summary: string;
}

export interface RecoveryRunDetail {
  run_id: string;
  scenario_id: string;
  scenario_title: string;
  execution_mode: "deterministic_demo";
  status: RecoveryRunStatus;
  started_at: string;
  completed_at: string | null;
  shift_id: string;
  trigger: string;
  steps: RecoveryRunStepView[];
  outcome: string | null;
  human_decision_required: boolean;
  interrupt_id: string | null;
  attention_budget_before: number;
  attention_budget_after: number;
  attention_budget_delta: number;
  final_shift: ShiftSummary | null;
  error: string | null;
}

export interface RunDemoScenarioResponse {
  duplicate: boolean;
  run: RecoveryRunDetail;
}

export interface DemoResetResponse {
  status: "reset";
  execution_mode: "deterministic_demo";
  workspace_id: "org:riverside";
  reset_at: string;
  shifts_restored: number;
  volunteers_restored: number;
  runs_cleared: number;
}

export interface VolunteerSummaryView {
  volunteer_id: string;
  display_name: string;
  roles: Role[];
  status: VolunteerOperationalStatus;
  available_shift_count: number;
  availability_summary: string;
  current_assignment_count: number;
  constraints: string[];
}

export interface VolunteerAssignmentView {
  assignment_id: string;
  role: Role;
  confirmed_at: string;
  shift: RelatedShiftView;
}

export interface VolunteerDetailView extends VolunteerSummaryView {
  available_shifts: RelatedShiftView[];
  assignments: VolunteerAssignmentView[];
  recent_activity: DecisionFeedItem[];
  contact_load_summary: "Not yet tracked";
}

export interface ShiftSummary {
  shift_id: string;
  site_id: string;
  site_name: string;
  starts_at: string;
  ends_at: string;
  coverage: RoleCoverage[];
  gap_count: number;
  gap_statuses: GapStatus[];
  status: ShiftOperationalStatus;
}

export interface ShiftDetail extends ShiftSummary {
  organisation_id: string;
  assignments: AssignmentView[];
  gaps: GapSummary[];
  ranked_candidates: RankedCandidateView[];
  pending_effects: PendingEffectCompactView[];
  needs_attention: InterruptCompactView[];
  recent_activity: DecisionFeedItem[];
}

export interface DashboardSummary {
  generated_at: string;
  attention_budget: AttentionBudgetView;
  counts: DashboardCounts;
  needs_attention: InterruptCompactView[];
  active_operations: ShiftSummary[];
  recent_activity: DecisionFeedItem[];
}
