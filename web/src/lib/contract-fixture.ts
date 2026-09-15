import fixture from "@/lib/fixtures/ui-api.json";
import type {
  AttentionBudgetView,
  DashboardSummary,
  HealthResponse,
  PendingEffectCompactView,
  ShiftDetail,
  ShiftSummary,
} from "@/lib/types";

export interface UiApiContractFixture {
  health: HealthResponse;
  attention_budget: AttentionBudgetView;
  dashboard: DashboardSummary;
  shifts: ShiftSummary[];
  shift_detail: ShiftDetail;
  pending: PendingEffectCompactView[];
}

// The same JSON is parsed by Pydantic in the backend contract test. This cast
// makes TypeScript consume that validated fixture as the UI-facing contract.
export const uiApiContractFixture = fixture as UiApiContractFixture;
