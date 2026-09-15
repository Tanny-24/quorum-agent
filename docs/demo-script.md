# QUORUM Demo Script

The original hackathon recording script has been superseded by the practical, browser-first [Local Demo Guide](local-demo-guide.md).

Use that guide for the final 3–5 minute interview flow. It demonstrates Scenario B, Scenario C, Shift state, Decision Feed, Human Decisions, and the Attention Budget through `deterministic_demo`, without consuming Bedrock/Gemini quota or sending Telegram messages.

Live provider evidence is separate and optional during a presentation:

- `scripts/validate_bedrock.py` performs the bounded Bedrock checks when a standard AWS credential chain is available.
- `scripts/run_agent_demo.py` retains the earlier opt-in Gemini proof.

Never display `.env`, AWS identity data, credentials, provider identifiers tied to a real account, or raw channel payloads.
