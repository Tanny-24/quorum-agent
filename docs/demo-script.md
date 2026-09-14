# QUORUM 4-minute demo script

## Before recording

~~~bash
cd /path/to/quorum-agent
source .venv/bin/activate
PYTHONPATH=. python -m scripts.run_agent_demo
~~~

Run once before recording to confirm quota is available. Never display .env, credentials, local paths, or private Telegram payloads. Keep the successful JSON visible or record the command after the free-tier window resets.

## 0:00–0:30 — problem and audience

Say: “A cancellation is not solved by another notification. Volunteer operations teams still have to find eligible help, negotiate constraints, prevent double-booking, and decide what deserves interruption. QUORUM recovers synthetic Riverside Food Bank staffing while treating human attention as a limited resource.”

## 0:30–0:55 — Attention Budget

Show the GREEN/YELLOW/RED/SILENT diagram. Say: “Routine, reversible work can execute or settle quietly. Consequential uncertainty spends a limited Attention Budget. Layer-0 safety topics always reach a human, regardless of budget.”

## 0:55–1:20 — Strands architecture

Show quorum/agents/models.py, then the Coordinator and Negotiator factories. Say: “Both roles are real Strands agents using Google Gemini. The provider is configurable, but code retains authority over ranking, eligibility, routing, capacity, and idempotency. LLM proposes; deterministic code disposes.”

## 1:20–2:40 — real Gemini-backed demo

Show the successful scripts.run_agent_demo JSON. Point to:

- provider: gemini and model: gemini-3.6-flash;
- Coordinator tool_uses containing get_shift;
- Negotiator session nego:shift-2:vol-04 and find_transport_option;
- two separate Negotiator responses;
- structured ACCEPT_IF and canonical condition: transport;
- confirmed: true and gap_resolved: true.

Say: “A synthetic cancellation created a driver gap. Deterministic ranking selected an eligible candidate. Gemini chose existing read tools, interpreted ‘can do but I need a ride,’ and continued a two-turn negotiation. Deterministic services resolved transport, capacity, assignment, and the gap.”

## 2:40–3:15 — RED safety and human decision

Point to the safety block and injection result. Say: “An injury and complaint become OUT_OF_SCOPE, route RED, and persist one human interrupt. Prompt injection remains UNCLEAR; it cannot mark an assignment confirmed or override application policy.”

## 3:15–3:40 — Telegram and decision ledger

Show quorum/channels/telegram.py and a sanitized decision-feed response. Say: “The provider-neutral Telegram adapter has real inbound and outbound validation. Every material routing and assignment decision enters an inspectable ledger. The recording sends no live message, avoiding duplicate smoke traffic.”

## 3:40–4:00 — impact and future

Say: “QUORUM combines real Strands orchestration and Gemini tool calling with deterministic safety, durable sessions, settlement windows, and attention-aware escalation. Bedrock remains a configurable future provider after AWS account activation; it is not part of this demonstrated path.”
