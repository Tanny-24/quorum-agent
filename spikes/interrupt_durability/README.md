# Strands Interrupt Durability Technical Spike

This isolated Phase 0 spike tests one QUORUM architecture assumption: a Strands `BeforeToolCallEvent` interrupt can be persisted by `FileSessionManager`, restored by a fresh `Agent` in a new Python process, and approved or vetoed before the gated side effect runs. This is not production QUORUM.

The read-only `list_volunteers` tool is ungated. The gated `send_message` tool does not contact anyone; it appends a JSON record to `_effects.log`. Its SHA-256 idempotency key is derived only from the recipient and body. A local file lock makes the check-and-append atomic between processes.

## Environment

Python 3.13 was used for this spike because Python 3.12 was unavailable locally.

```bash
cd ~/Desktop/Pro/quorum-agent
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The normal commands use Amazon Bedrock. Configure AWS credentials and a region first. The SDK defaults to `us-west-2`; override the model with `QUORUM_SPIKE_MODEL_ID` if needed.

## Approval path

Each command is a separate process:

```bash
.venv/bin/python spikes/interrupt_durability/spike_verify.py reset
.venv/bin/python spikes/interrupt_durability/spike_run.py --scenario approval
.venv/bin/python spikes/interrupt_durability/spike_resume.py y
.venv/bin/python spikes/interrupt_durability/spike_verify.py approval
```

The run command must report `RUN_STOP_REASON=interrupt`, with no `_effects.log`. The resume should end normally, and the verifier must report one effect whose PID equals the resume PID and differs from the original PID.

## Veto path

```bash
.venv/bin/python spikes/interrupt_durability/spike_verify.py reset
.venv/bin/python spikes/interrupt_durability/spike_run.py --scenario veto
.venv/bin/python spikes/interrupt_durability/spike_resume.py n
.venv/bin/python spikes/interrupt_durability/spike_verify.py veto
```

The veto verifier passes only when there are zero effects.

## Automated offline checks

```bash
.venv/bin/python -m pytest spikes/interrupt_durability/test_spike.py -v
```

These tests deliberately use a deterministic custom model because they verify process-boundary SDK behavior without network access. They do not count as a Bedrock acceptance run. The Strands `Agent`, hook, tools, session persistence, interrupts, and subprocess boundaries remain real.

Generated and ignored artifacts are `_state/`, `_effects.log`, `_effects.lock`, `_pending.json`, `__pycache__/`, `.pytest_cache/`, and `.venv/`. The reset command removes only generated spike state under the active runtime directory.
