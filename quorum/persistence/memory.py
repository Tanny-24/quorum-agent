"""Thread-safe deterministic in-memory store for local use and tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from quorum.domain.models import (
    Assignment,
    AttentionBudget,
    Gap,
    InterruptRecord,
    InterruptStatus,
    LedgerEntry,
    NegotiationThread,
    Organisation,
    PendingEffect,
    PendingStatus,
    RecoveryRun,
    Role,
    Shift,
    Site,
    Volunteer,
)


class MemoryStore:
    """Keep domain records with atomic transitions guarded by one local lock."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.organisations: dict[str, Organisation] = {}
        self.sites: dict[str, Site] = {}
        self.volunteers: dict[str, Volunteer] = {}
        self.shifts: dict[str, Shift] = {}
        self.assignments: dict[str, Assignment] = {}
        self.gaps: dict[str, Gap] = {}
        self.negotiations: dict[str, NegotiationThread] = {}
        self.pending: dict[str, PendingEffect] = {}
        self.interrupts: dict[str, InterruptRecord] = {}
        self.ledger: list[LedgerEntry] = []
        self.budgets: dict[str, AttentionBudget] = {}
        self.processed_events: set[str] = set()
        self.executed_effects: dict[str, dict[str, Any]] = {}
        self._budget_decisions: set[str] = set()
        self.recovery_runs: dict[str, RecoveryRun] = {}
        self._recovery_run_keys: dict[str, str] = {}

    def seed(
        self,
        organisations: list[Organisation],
        sites: list[Site],
        volunteers: list[Volunteer],
        shifts: list[Shift],
    ) -> None:
        with self._lock:
            self.organisations.update({item.id: deepcopy(item) for item in organisations})
            self.sites.update({item.id: deepcopy(item) for item in sites})
            self.volunteers.update({item.id: deepcopy(item) for item in volunteers})
            self.shifts.update({item.id: deepcopy(item) for item in shifts})

    def reset_synthetic(
        self,
        organisations: list[Organisation],
        sites: list[Site],
        volunteers: list[Volunteer],
        shifts: list[Shift],
    ) -> int:
        """Replace only the in-memory synthetic workspace's operational state."""
        with self._lock:
            runs_cleared = len(self.recovery_runs)
            self.organisations = {item.id: deepcopy(item) for item in organisations}
            self.sites = {item.id: deepcopy(item) for item in sites}
            self.volunteers = {item.id: deepcopy(item) for item in volunteers}
            self.shifts = {item.id: deepcopy(item) for item in shifts}
            self.assignments.clear()
            self.gaps.clear()
            self.negotiations.clear()
            self.pending.clear()
            self.interrupts.clear()
            self.ledger.clear()
            self.budgets.clear()
            self.processed_events.clear()
            self.executed_effects.clear()
            self._budget_decisions.clear()
            self.recovery_runs.clear()
            self._recovery_run_keys.clear()
            return runs_cleared

    def get_shift(self, shift_id: str) -> Shift | None:
        with self._lock:
            value = self.shifts.get(shift_id)
            return deepcopy(value)

    def get_site(self, site_id: str) -> Site | None:
        with self._lock:
            return deepcopy(self.sites.get(site_id))

    def list_shifts(self) -> list[Shift]:
        with self._lock:
            return deepcopy(list(self.shifts.values()))

    def get_volunteer(self, volunteer_id: str) -> Volunteer | None:
        with self._lock:
            return deepcopy(self.volunteers.get(volunteer_id))

    def list_volunteers(self) -> list[Volunteer]:
        with self._lock:
            return deepcopy(list(self.volunteers.values()))

    def list_assignments(self, shift_id: str) -> list[Assignment]:
        with self._lock:
            return deepcopy([item for item in self.assignments.values() if item.shift_id == shift_id])

    def list_assignments_for_volunteer(
        self, volunteer_id: str
    ) -> list[Assignment]:
        with self._lock:
            return deepcopy(
                [
                    item
                    for item in self.assignments.values()
                    if item.volunteer_id == volunteer_id
                ]
            )

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        with self._lock:
            return deepcopy(self.assignments.get(assignment_id))

    def upsert_gap(self, gap: Gap) -> Gap:
        with self._lock:
            existing = self.gaps.get(gap.id)
            if existing is not None:
                return deepcopy(existing)
            self.gaps[gap.id] = deepcopy(gap)
            return deepcopy(gap)

    def update_gap(self, gap: Gap) -> Gap:
        with self._lock:
            self.gaps[gap.id] = deepcopy(gap)
            return deepcopy(gap)

    def get_gap(self, gap_id: str) -> Gap | None:
        with self._lock:
            return deepcopy(self.gaps.get(gap_id))

    def list_gaps(self) -> list[Gap]:
        with self._lock:
            return deepcopy(list(self.gaps.values()))

    def record_event_once(self, key: str) -> bool:
        with self._lock:
            if key in self.processed_events:
                return False
            self.processed_events.add(key)
            return True

    def record_effect_once(self, key: str, result: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            existing = self.executed_effects.get(key)
            if existing is not None:
                return False, deepcopy(existing)
            self.executed_effects[key] = deepcopy(result)
            return True, deepcopy(result)

    def begin_effect(self, key: str) -> tuple[bool, dict[str, Any]]:
        """Atomically reserve an external effect before the provider call."""
        with self._lock:
            existing = self.executed_effects.get(key)
            if existing is not None:
                return False, deepcopy(existing)
            marker = {"status": "executing"}
            self.executed_effects[key] = marker
            return True, deepcopy(marker)

    def complete_effect(self, key: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.executed_effects[key] = deepcopy(result)
            return deepcopy(result)

    def confirm_assignment(
        self, assignment: Assignment, required_count: int
    ) -> tuple[bool, Assignment | None, str]:
        with self._lock:
            duplicate = next(
                (
                    item
                    for item in self.assignments.values()
                    if item.shift_id == assignment.shift_id
                    and item.volunteer_id == assignment.volunteer_id
                    and item.role == assignment.role
                ),
                None,
            )
            if duplicate:
                return True, deepcopy(duplicate), "already_confirmed"
            filled = sum(
                1
                for item in self.assignments.values()
                if item.shift_id == assignment.shift_id and item.role == assignment.role
            )
            if filled >= required_count:
                return False, None, "already_filled"
            self.assignments[assignment.id] = deepcopy(assignment)
            return True, deepcopy(assignment), "confirmed"

    def create_pending(self, pending: PendingEffect) -> PendingEffect:
        with self._lock:
            existing = next(
                (item for item in self.pending.values() if item.idempotency_key == pending.idempotency_key), None
            )
            if existing:
                return deepcopy(existing)
            self.pending[pending.id] = deepcopy(pending)
            return deepcopy(pending)

    def get_pending(self, pending_id: str) -> PendingEffect | None:
        with self._lock:
            return deepcopy(self.pending.get(pending_id))

    def list_pending(self) -> list[PendingEffect]:
        with self._lock:
            return deepcopy(list(self.pending.values()))

    def list_due_pending(self, now: datetime) -> list[PendingEffect]:
        with self._lock:
            return deepcopy(
                [item for item in self.pending.values() if item.status == PendingStatus.PENDING and item.settle_at <= now]
            )

    def transition_pending(
        self, pending_id: str, expected: PendingStatus, target: PendingStatus, result: dict[str, Any] | None = None
    ) -> tuple[bool, PendingEffect | None]:
        with self._lock:
            item = self.pending.get(pending_id)
            if item is None or item.status != expected:
                return False, deepcopy(item)
            item.status = target
            item.updated_at = datetime.now(timezone.utc)
            item.result = deepcopy(result)
            return True, deepcopy(item)

    def create_interrupt(self, record: InterruptRecord) -> InterruptRecord:
        with self._lock:
            existing = next(
                (item for item in self.interrupts.values() if item.idempotency_key == record.idempotency_key), None
            )
            if existing:
                return deepcopy(existing)
            self.interrupts[record.id] = deepcopy(record)
            return deepcopy(record)

    def get_interrupt(self, record_id: str) -> InterruptRecord | None:
        with self._lock:
            return deepcopy(self.interrupts.get(record_id))

    def update_interrupt(self, record: InterruptRecord) -> InterruptRecord:
        with self._lock:
            if record.id not in self.interrupts:
                raise KeyError(record.id)
            self.interrupts[record.id] = deepcopy(record)
            return deepcopy(record)

    def claim_interrupt(
        self, record_id: str, expected_version: int | None = None
    ) -> tuple[bool, InterruptRecord | None]:
        with self._lock:
            item = self.interrupts.get(record_id)
            if (
                item is None
                or item.status != InterruptStatus.OPEN
                or (expected_version is not None and item.version != expected_version)
            ):
                return False, deepcopy(item)
            item.status = InterruptStatus.RESOLVING
            item.version += 1
            return True, deepcopy(item)

    def complete_interrupt(
        self,
        record_id: str,
        decision: str,
        *,
        note: str | None = None,
        actor: str | None = None,
        outcome: str | None = None,
    ) -> InterruptRecord:
        with self._lock:
            item = self.interrupts[record_id]
            if item.status != InterruptStatus.RESOLVING:
                raise RuntimeError("Interrupt was not claimed")
            item.status = InterruptStatus.RESOLVED
            item.decision = decision
            item.decision_note = note
            item.decision_actor = actor
            item.resolution_outcome = outcome
            item.resolved_at = datetime.now(timezone.utc)
            item.version += 1
            return deepcopy(item)

    def release_interrupt(self, record_id: str) -> InterruptRecord:
        with self._lock:
            item = self.interrupts[record_id]
            if item.status == InterruptStatus.RESOLVING:
                item.status = InterruptStatus.OPEN
                item.version += 1
            return deepcopy(item)

    def resolve_interrupt(self, record_id: str, decision: str) -> tuple[bool, InterruptRecord | None]:
        claimed, item = self.claim_interrupt(record_id)
        if not claimed:
            return False, item
        return True, self.complete_interrupt(record_id, decision)

    def list_open_interrupts(self) -> list[InterruptRecord]:
        with self._lock:
            return deepcopy([item for item in self.interrupts.values() if item.status == InterruptStatus.OPEN])

    def list_interrupts(
        self, status: InterruptStatus | None = None
    ) -> list[InterruptRecord]:
        with self._lock:
            items = list(self.interrupts.values())
            if status is not None:
                items = [item for item in items if item.status == status]
            return deepcopy(items)

    def get_budget(self, budget_id: str, allowance: int = 2) -> AttentionBudget:
        with self._lock:
            if budget_id not in self.budgets:
                self.budgets[budget_id] = AttentionBudget(id=budget_id, allowance=allowance)
            return deepcopy(self.budgets[budget_id])

    def spend_budget_once(self, budget_id: str, decision_id: str, override: bool = False) -> AttentionBudget:
        with self._lock:
            budget = self.budgets.setdefault(budget_id, AttentionBudget(id=budget_id))
            if decision_id in self._budget_decisions:
                return deepcopy(budget)
            self._budget_decisions.add(decision_id)
            if override:
                budget.overrides += 1
            else:
                budget.spent += 1
            budget.history.append({"decision_id": decision_id, "override": override})
            return deepcopy(budget)

    def append_ledger(self, entry: LedgerEntry) -> None:
        with self._lock:
            if not any(item.id == entry.id for item in self.ledger):
                self.ledger.append(deepcopy(entry))

    def list_ledger(self) -> list[LedgerEntry]:
        with self._lock:
            return deepcopy(self.ledger)

    def save_negotiation(self, thread: NegotiationThread) -> NegotiationThread:
        with self._lock:
            self.negotiations[thread.id] = deepcopy(thread)
            return deepcopy(thread)

    def get_negotiation(self, thread_id: str) -> NegotiationThread | None:
        with self._lock:
            return deepcopy(self.negotiations.get(thread_id))

    def list_negotiations(self) -> list[NegotiationThread]:
        with self._lock:
            return deepcopy(list(self.negotiations.values()))

    def create_recovery_run(
        self, run: RecoveryRun
    ) -> tuple[bool, RecoveryRun]:
        with self._lock:
            existing_id = self._recovery_run_keys.get(run.idempotency_key)
            if existing_id:
                return False, deepcopy(self.recovery_runs[existing_id])
            self.recovery_runs[run.id] = deepcopy(run)
            self._recovery_run_keys[run.idempotency_key] = run.id
            return True, deepcopy(run)

    def update_recovery_run(self, run: RecoveryRun) -> RecoveryRun:
        with self._lock:
            if run.id not in self.recovery_runs:
                raise KeyError(run.id)
            self.recovery_runs[run.id] = deepcopy(run)
            return deepcopy(run)

    def get_recovery_run(self, run_id: str) -> RecoveryRun | None:
        with self._lock:
            return deepcopy(self.recovery_runs.get(run_id))

    def list_recovery_runs(self) -> list[RecoveryRun]:
        with self._lock:
            return deepcopy(list(self.recovery_runs.values()))
