"""Shared implementation for the QUORUM Phase 0 interrupt durability spike."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from strands import Agent, tool
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.models import BedrockModel, Model
from strands.session import FileSessionManager

SPIKE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = Path(os.environ.get("QUORUM_SPIKE_RUNTIME_DIR", SPIKE_DIR)).resolve()
STATE_DIR = RUNTIME_DIR / "_state"
SESSION_STORAGE_DIR = STATE_DIR / "sessions"
EFFECTS_LOG = RUNTIME_DIR / "_effects.log"
EFFECTS_LOCK = RUNTIME_DIR / "_effects.lock"
PENDING_FILE = RUNTIME_DIR / "_pending.json"

AGENT_ID = "quorum-phase0-agent"
DEFAULT_SESSION_ID = "quorum-phase0-session"
DEFAULT_RECIPIENT = "Sam T."
DEFAULT_BODY = "Can you help at the shelter tonight?"
DEFAULT_REGION = "us-west-2"
DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically replace a small JSON metadata file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def idempotency_key(recipient: str, body: str) -> str:
    """Derive a stable key from logical action inputs only."""
    canonical = json.dumps(
        {"body": body, "recipient": recipient},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_effects() -> list[dict[str, Any]]:
    """Read and validate the append-only JSON-lines proof log."""
    if not EFFECTS_LOG.exists():
        return []

    effects: list[dict[str, Any]] = []
    for line_number, line in enumerate(EFFECTS_LOG.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Invalid effect record at line {line_number}")
        effects.append(value)
    return effects


def record_send_effect(recipient: str, body: str) -> dict[str, Any]:
    """Append one logical send, suppressing a previously recorded stable key."""
    key = idempotency_key(recipient, body)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    # The lock makes the check-and-append operation safe across local processes.
    with EFFECTS_LOCK.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        existing = read_effects()
        if any(effect.get("idempotency_key") == key for effect in existing):
            return {
                "status": "duplicate_suppressed",
                "idempotency_key": key,
                "recipient": recipient,
            }

        effect = {
            "body": body,
            "idempotency_key": key,
            "pid": os.getpid(),
            "recipient": recipient,
            "timestamp": utc_now(),
        }
        with EFFECTS_LOG.open("a", encoding="utf-8") as effects_file:
            effects_file.write(json.dumps(effect, ensure_ascii=False, sort_keys=True) + "\n")
            effects_file.flush()
            os.fsync(effects_file.fileno())
        return {"status": "sent", **effect}


@tool
def list_volunteers() -> list[str]:
    """Return the example volunteer names; this read-only tool is never gated."""
    print(f"READ_TOOL_EXECUTED pid={os.getpid()}")
    return ["Sam T.", "Priya K.", "Dev M."]


@tool
def send_message(recipient: str, body: str) -> dict[str, Any]:
    """Represent a message send by appending an idempotent record to the proof log.

    Args:
        recipient: Volunteer who should receive the example message.
        body: Message body to record.
    """
    result = record_send_effect(recipient, body)
    print(f"SIDE_EFFECT_{result['status'].upper()} pid={os.getpid()} key={result['idempotency_key']}")
    return result


class ApprovalHook(HookProvider):
    """Interrupt only send_message before its side effect executes."""

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.approve_send)

    def approve_send(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != "send_message":
            return

        inputs = event.tool_use.get("input", {})
        recipient = str(inputs.get("recipient", ""))
        body = str(inputs.get("body", ""))
        reason = {
            "action": "send_message",
            "body": body,
            "idempotency_key": idempotency_key(recipient, body),
            "recipient": recipient,
        }
        response = event.interrupt("approve_send_message", reason=reason)
        approved = response is True or (isinstance(response, str) and response.lower() in {"y", "yes", "approve"})
        if not approved:
            event.cancel_tool = "Human vetoed send_message; no external side effect was executed."


def bedrock_model() -> BedrockModel:
    """Construct the real model used by the acceptance commands."""
    session = boto3.Session()
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or session.region_name
    region = region or DEFAULT_REGION
    model_id = os.environ.get("QUORUM_SPIKE_MODEL_ID", DEFAULT_MODEL_ID)
    return BedrockModel(region_name=region, model_id=model_id, temperature=0, max_tokens=256)


def create_agent(session_id: str, model: Model | None = None) -> Agent:
    """Create a fresh Agent backed by explicit persistent session storage."""
    SESSION_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir=str(SESSION_STORAGE_DIR),
    )
    return Agent(
        agent_id=AGENT_ID,
        callback_handler=None,
        hooks=[ApprovalHook()],
        model=model or bedrock_model(),
        session_manager=session_manager,
        system_prompt=(
            "You are a narrow technical-spike agent. Follow the user's exact requested tool sequence. "
            "Use list_volunteers for reads and send_message for the single requested send."
        ),
        tools=[list_volunteers, send_message],
    )


def initial_prompt() -> str:
    """Return the fixed prompt that drives the real model through both tools."""
    return (
        "First call list_volunteers. After seeing its result, call send_message exactly once with "
        f"recipient {DEFAULT_RECIPIENT!r} and body {DEFAULT_BODY!r}. Do not merely describe the calls."
    )
