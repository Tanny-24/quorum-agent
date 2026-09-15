from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient

from quorum.api.app import AppContext, create_app
from quorum.api.schemas import (
    AttentionBudgetView,
    DashboardSummary,
    HealthResponse,
    PendingEffectCompactView,
    ShiftDetail,
    ShiftSummary,
)
from quorum.config import Settings
from quorum.data.loader import seed_store
from quorum.domain.models import PendingStatus, Role
from quorum.persistence.memory import MemoryStore
from quorum.services.candidate_ranker import CandidateRanker


FIXED_NOW = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)


def product_context(*, attention_budget: int = 5) -> AppContext:
    store = seed_store(MemoryStore(), FIXED_NOW)
    settings = Settings(
        attention_budget=attention_budget,
        gemini_api_key="must-not-reach-ui",
        telegram_bot_token="must-not-reach-ui",
        telegram_chat_id="must-not-reach-ui",
    )
    return AppContext(store=store, settings=settings)


def test_dashboard_uses_real_state_and_safe_projections() -> None:
    context = product_context()
    client = TestClient(create_app(context))
    context.pending.create(
        "send_message",
        "dashboard-pending",
        {"shift_id": "shift-1", "body": "private-payload-must-not-reach-ui"},
        now=FIXED_NOW,
        delay_minutes=10,
    )
    context.interrupts.create(
        "nego:shift-1:vol-09",
        "dashboard-interrupt",
        {
            "classification": {
                "safety_reason": "injury",
                "raw": "private-payload-must-not-reach-ui",
            },
            "routing": {
                "reason": "layer_0:injury",
                "budget_spent": True,
                "budget_override": False,
            },
            "inputs": {
                "shift_id": "shift-1",
                "volunteer_id": "vol-09",
                "body": "private-payload-must-not-reach-ui",
            },
        },
    )
    event = {"shift_id": "shift-1", "idempotency_key": "dashboard-gap"}
    assert client.post("/events/cancel", json=event).status_code == 200

    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["attention_budget"] == {
        "allowance": 5,
        "spent": 0,
        "remaining": 5,
        "overrides": 0,
    }
    assert body["counts"] == {
        "total_shifts": 6,
        "open_gaps": 2,
        "active_recoveries": 0,
        "pending_effects": 1,
        "human_decisions_required": 1,
    }
    assert body["needs_attention"][0]["safety_reason"] == "injury"
    assert body["active_operations"][0]["shift_id"] == "shift-1"
    serialized = response.text
    assert "must-not-reach-ui" not in serialized
    assert "private-payload-must-not-reach-ui" not in serialized


def test_shifts_are_typed_backend_derived_summaries() -> None:
    context = product_context()
    client = TestClient(create_app(context))

    response = client.get("/shifts")
    assert response.status_code == 200
    shifts = response.json()
    assert len(shifts) == 6
    first = shifts[0]
    assert first["shift_id"] == "shift-1"
    assert first["site_name"] == "River Hall"
    assert first["status"] == "SCHEDULED"
    assert first["gap_count"] == 0
    assert first["coverage"] == [
        {"role": "driver", "required": 1, "assigned": 0, "shortfall": 1},
        {"role": "sorter", "required": 2, "assigned": 0, "shortfall": 2},
    ]

    client.post(
        "/events/no-show",
        json={"shift_id": "shift-1", "idempotency_key": "typed-shift-gap"},
    )
    changed = client.get("/shifts").json()[0]
    assert changed["status"] == "NEEDS_COVERAGE"
    assert changed["gap_count"] == 2
    assert changed["gap_statuses"] == ["DETECTED"]


def test_shift_detail_uses_existing_ranker_and_returns_404() -> None:
    context = product_context()
    client = TestClient(create_app(context))
    client.post(
        "/events/cancel",
        json={"shift_id": "shift-1", "idempotency_key": "detail-gap"},
    )

    response = client.get("/shifts/shift-1")
    assert response.status_code == 200
    detail = response.json()
    expected_driver_ids = [
        item.volunteer_id
        for item in CandidateRanker(context.store).rank("shift-1", Role.DRIVER)[:5]
    ]
    actual_driver_ids = [
        item["volunteer"]["volunteer_id"]
        for item in detail["ranked_candidates"]
        if item["role"] == "driver"
    ]
    assert actual_driver_ids == expected_driver_ids
    assert len(detail["gaps"]) == 2
    assert detail["assignments"] == []
    keys: set[str] = set()

    def collect_keys(value) -> None:
        if isinstance(value, dict):
            keys.update(value)
            for child in value.values():
                collect_keys(child)
        elif isinstance(value, list):
            for child in value:
                collect_keys(child)

    collect_keys(detail)
    assert "age" not in keys
    assert "background_check" not in keys
    assert client.get("/shifts/unknown").status_code == 404


def test_attention_budget_reads_the_authoritative_store_record() -> None:
    context = product_context(attention_budget=5)
    client = TestClient(create_app(context))
    context.store.spend_budget_once("budget:riverside", "ui-budget-decision")

    response = client.get("/attention-budget")
    assert response.status_code == 200
    assert response.json() == {
        "allowance": 5,
        "spent": 1,
        "remaining": 4,
        "overrides": 0,
    }


def test_pending_supports_status_filters_without_exposing_payloads() -> None:
    context = product_context()
    client = TestClient(create_app(context))
    pending = context.pending.create(
        "send_message",
        "pending-visible",
        {
            "shift_id": "shift-1",
            "volunteer_id": "vol-01",
            "body": "private-payload-must-not-reach-ui",
        },
        now=FIXED_NOW,
        delay_minutes=10,
    )
    settled = context.pending.create(
        "send_message",
        "pending-settled",
        {"shift_id": "shift-2", "body": "another-private-payload"},
        now=FIXED_NOW,
        delay_minutes=0,
    )
    context.store.transition_pending(
        settled.id, PendingStatus.PENDING, PendingStatus.SETTLING
    )
    context.store.transition_pending(
        settled.id, PendingStatus.SETTLING, PendingStatus.SETTLED
    )

    all_items = client.get("/pending")
    assert all_items.status_code == 200
    assert len(all_items.json()) == 2
    assert "private-payload" not in all_items.text
    pending_items = client.get("/pending", params={"status": "PENDING"}).json()
    assert [item["pending_id"] for item in pending_items] == [pending.id]
    assert client.get("/pending", params={"status": "FAILED"}).json() == []
    assert client.get("/pending", params={"status": "INVALID"}).status_code == 422


def test_openapi_names_every_ui_read_contract() -> None:
    schema = create_app(product_context()).openapi()
    assert schema["paths"]["/dashboard"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/DashboardSummary")
    assert schema["paths"]["/shifts"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["items"]["$ref"].endswith("/ShiftSummary")
    assert schema["paths"]["/shifts/{shift_id}"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/ShiftDetail")
    assert schema["paths"]["/attention-budget"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"].endswith("/AttentionBudgetView")
    assert schema["paths"]["/pending"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["items"]["$ref"].endswith("/PendingEffectCompactView")


def test_shared_frontend_fixture_validates_against_pydantic_contracts() -> None:
    fixture_path = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "lib"
        / "fixtures"
        / "ui-api.json"
    )
    fixture = json.loads(fixture_path.read_text())

    assert HealthResponse.model_validate(fixture["health"]).model_dump(
        mode="json"
    ) == fixture["health"]
    assert AttentionBudgetView.model_validate(
        fixture["attention_budget"]
    ).model_dump(mode="json") == fixture["attention_budget"]
    assert DashboardSummary.model_validate(fixture["dashboard"]).model_dump(
        mode="json"
    ) == fixture["dashboard"]
    assert [
        ShiftSummary.model_validate(item).model_dump(mode="json")
        for item in fixture["shifts"]
    ] == fixture["shifts"]
    assert ShiftDetail.model_validate(fixture["shift_detail"]).model_dump(
        mode="json"
    ) == fixture["shift_detail"]
    assert [
        PendingEffectCompactView.model_validate(item).model_dump(mode="json")
        for item in fixture["pending"]
    ] == fixture["pending"]
