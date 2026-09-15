from __future__ import annotations

from fastapi.testclient import TestClient

from quorum.api.app import AppContext, create_app
from quorum.config import Settings
from quorum.domain.models import GapStatus, ReplyIntent, RoutingClass


def client_for(store) -> tuple[AppContext, TestClient]:
    context = AppContext(
        store=store,
        settings=Settings(
            attention_budget=5,
            gemini_api_key="must-not-run",
            telegram_bot_token="must-not-send",
            telegram_chat_id="must-not-send",
        ),
    )
    return context, TestClient(create_app(context))


def run_scenario(client: TestClient, scenario_id: str, key: str) -> dict:
    response = client.post(
        f"/demo/scenarios/{scenario_id}/run",
        json={
            "idempotency_key": key,
            "execution_mode": "deterministic_demo",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_demo_scenario_catalog_is_typed_and_truthful(store) -> None:
    _, client = client_for(store)

    response = client.get("/demo/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert [item["id"] for item in scenarios] == [
        "scenario-a",
        "scenario-b",
        "scenario-c",
    ]
    assert {item["execution_mode"] for item in scenarios} == {
        "deterministic_demo"
    }
    assert [item["expected_route"] for item in scenarios] == [
        "GREEN",
        "YELLOW",
        "RED",
    ]


def test_scenario_a_completes_real_assignments_without_attention(store) -> None:
    context, client = client_for(store)

    result = run_scenario(client, "scenario-a", "phase3-scenario-a")
    run = result["run"]

    assert result["duplicate"] is False
    assert run["status"] == "COMPLETED"
    assert run["execution_mode"] == "deterministic_demo"
    assert run["human_decision_required"] is False
    assert run["attention_budget_delta"] == 0
    assert run["final_shift"]["status"] == "FULLY_STAFFED"
    assert len(context.store.list_assignments("shift-1")) == 3
    assert all(
        item.status == GapStatus.RESOLVED
        for item in context.store.list_gaps()
        if item.shift_id == "shift-1"
    )
    assert context.store.list_open_interrupts() == []
    assert {step["step_type"] for step in run["steps"]} >= {
        "event",
        "gap_detection",
        "ranking",
        "assignment",
        "gap_resolution",
    }


def test_scenario_b_uses_real_accept_if_transport_and_assignment(store) -> None:
    context, client = client_for(store)

    result = run_scenario(client, "scenario-b", "phase3-scenario-b")
    run = result["run"]

    assert run["status"] == "COMPLETED"
    assert run["human_decision_required"] is False
    assert run["attention_budget_delta"] == 0
    assert run["final_shift"]["status"] == "FULLY_STAFFED"
    assert len(context.store.list_assignments("shift-2")) == 3
    entries = context.store.list_ledger()
    conditional = [
        entry
        for entry in entries
        if entry.category == "reply" and entry.decision == ReplyIntent.ACCEPT_IF
    ]
    assert len(conditional) == 1
    assert conditional[0].reason == "condition:transport"
    transport = [
        entry
        for entry in entries
        if entry.category == "transport"
        and entry.decision == "CONDITION_RESOLVED"
    ]
    assert len(transport) == 1
    assert transport[0].routing_class == RoutingClass.GREEN
    assert any(step["step_type"] == "transport" for step in run["steps"])
    feed = client.get("/feed", params={"shift_id": "shift-2"}).json()["items"]
    assert {item["category"] for item in feed} >= {
        "event",
        "ranking",
        "reply",
        "transport",
        "assignment",
        "gap",
    }


def test_scenario_c_uses_safety_route_and_persists_human_decision(store) -> None:
    context, client = client_for(store)

    result = run_scenario(client, "scenario-c", "phase3-scenario-c")
    run = result["run"]

    assert run["status"] == "WAITING_FOR_HUMAN"
    assert run["human_decision_required"] is True
    assert run["interrupt_id"]
    assert run["attention_budget_delta"] == 1
    assert context.store.get_interrupt(run["interrupt_id"]) is not None
    detail = client.get(f"/interrupts/{run['interrupt_id']}")
    assert detail.status_code == 200
    assert detail.json()["route"] == "RED"
    assert detail.json()["status"] == "OPEN"
    assert detail.json()["allowed_actions"] == ["APPROVE", "VETO"]
    assert client.get("/attention-budget").json()["spent"] == 1
    assert any(
        step["status"] == "WAITING_FOR_HUMAN" for step in run["steps"]
    )


def test_demo_run_is_idempotent_readable_and_unknown_is_404(store) -> None:
    context, client = client_for(store)
    first = run_scenario(client, "scenario-a", "phase3-idempotent")
    ledger_count = len(context.store.list_ledger())

    second = run_scenario(client, "scenario-a", "phase3-idempotent")

    assert second["duplicate"] is True
    assert second["run"]["run_id"] == first["run"]["run_id"]
    assert len(context.store.list_ledger()) == ledger_count
    run_id = first["run"]["run_id"]
    assert client.get(f"/demo/runs/{run_id}").json() == first["run"]
    assert [item["run_id"] for item in client.get("/demo/runs").json()] == [
        run_id
    ]
    assert client.get("/demo/runs/unknown").status_code == 404
    assert (
        client.post(
            "/demo/scenarios/unknown/run",
            json={"idempotency_key": "phase3-unknown"},
        ).status_code
        == 404
    )


def test_demo_reset_restores_only_the_synthetic_workspace(store) -> None:
    _, client = client_for(store)
    run_scenario(client, "scenario-c", "phase3-before-reset")

    response = client.post("/demo/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reset"
    assert body["workspace_id"] == "org:riverside"
    assert body["execution_mode"] == "deterministic_demo"
    assert body["shifts_restored"] == 6
    assert body["volunteers_restored"] == 36
    assert body["runs_cleared"] == 1
    assert client.get("/demo/runs").json() == []
    assert client.get("/interrupts").json() == []
    assert client.get("/pending").json() == []
    assert client.get("/feed").json()["items"] == []
    assert client.get("/attention-budget").json()["spent"] == 0
    assert all(item["status"] == "SCHEDULED" for item in client.get("/shifts").json())


def test_volunteer_projections_are_safe_filterable_and_contextual(store) -> None:
    _, client = client_for(store)
    run_scenario(client, "scenario-b", "phase3-volunteer-context")

    collection = client.get(
        "/volunteers",
        params={"role": "driver", "status": "ACTIVE", "available": True},
    )
    assert collection.status_code == 200
    assert collection.json()
    assert all("driver" in item["roles"] for item in collection.json())
    assigned = next(
        item for item in collection.json() if item["current_assignment_count"] > 0
    )
    detail = client.get(f"/volunteers/{assigned['volunteer_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["assignments"]
    assert payload["assignments"][0]["shift"]["site_name"] == "North Pantry"
    assert payload["recent_activity"]
    assert payload["contact_load_summary"] == "Not yet tracked"
    serialized = detail.text
    for private_field in (
        "age",
        "background_check",
        "archetype",
        "reliability_successes",
        "telegram",
        "must-not-run",
        "must-not-send",
        "I can do it, but I need a ride.",
    ):
        assert private_field not in serialized
    assert client.get("/volunteers/unknown").status_code == 404


def test_demo_mode_never_calls_model_or_telegram(store, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external provider must not run in deterministic_demo")

    monkeypatch.setattr("quorum.channels.telegram.TelegramChannel.send", forbidden)
    monkeypatch.setattr("quorum.agents.models.create_model", forbidden)
    _, client = client_for(store)

    assert run_scenario(
        client,
        "scenario-b",
        "phase3-no-provider-b",
    )["run"]["status"] == "COMPLETED"
    assert run_scenario(
        client,
        "scenario-c",
        "phase3-no-provider-c",
    )["run"]["status"] == "WAITING_FOR_HUMAN"


def test_demo_failure_is_preserved_as_a_safe_failed_run(store) -> None:
    context, client = client_for(store)
    for volunteer in context.store.volunteers.values():
        volunteer.active = False

    result = run_scenario(client, "scenario-a", "phase3-safe-failure")["run"]

    assert result["status"] == "FAILED"
    assert result["outcome"] == "Workflow did not complete"
    assert result["error"] == "Deterministic workflow failed (RuntimeError)."
    assert result["steps"][-1]["status"] == "FAILED"
