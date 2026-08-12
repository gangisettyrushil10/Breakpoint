# BreakPoint API

Deterministic financial stress-test service (FastAPI + Python).

## Setup

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The chat agent needs an OpenAI API key:

```bash
cp .env.example .env   # then add your key — .env is gitignored
```

Without it, `/health` and `/simulate` work normally and `/agent/chat` returns a
502 explaining what's missing. That degradation is deliberate: the deterministic
product shouldn't break because the AI feature isn't configured.

Default model is `gpt-5.6-luna` (~$1.80 per 1,000 chats). The model never
computes a number, so it doesn't need to be a strong one — override with
`OPENAI_MODEL` if you want to compare.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health)

## Test

```bash
pytest
```

## Endpoints

| Endpoint | What it does |
| --- | --- |
| `GET /health` | Liveness check. |
| `POST /simulate` | The deterministic engine. No LLM anywhere in this path. |
| `POST /agent/chat` | Chat agent. Routes to the same engine and explains the result. |

## The agent

`app/agent/` holds everything LLM-related; `app/simulation/`, `app/scenarios/`,
and `app/domain/` stay pure and know nothing about it.

```
app/agent/
  loop.py         bounded model <-> tool loop (max 5 iterations, 60s budget)
  provider.py     everything that knows OpenAI's wire format
  grounding.py    the ledger: which numbers a reply may contain
  guardrails.py   blocks dangerous advice, catches ungrounded figures
  prompts.py      system prompt — frozen, so the prompt cache holds
  ratelimit.py    per-IP token bucket for /agent/chat
  schemas.py      the /agent/chat wire contract
  tools/
    simulate.py       wraps the same pipeline as POST /simulate
    patch_profile.py  merges partial profile edits
    registry.py       name -> handler, plus the schemas the model sees
```

Two invariants hold this together, and both are tested:

- **The model never computes a number.** It cannot see the profile — the only
  way it learns anything about the user's money is by calling `simulate`, and
  the server supplies the profile, not the model.
- **The tool and the route cannot drift.** `tests/test_agent_tools.py` asserts
  `simulate` and `POST /simulate` return identical output for the same inputs.
  If you change one, change both.

### How ungrounded numbers are caught

`grounding.py` builds a **ledger** — the closed set of values the tool actually
returned — and checks every number in the reply against it. Numbers are
classified by their own surface form (`$3,000` is money-shaped, `9.4 months` is
months-shaped), so phrasing and word order don't matter.

An earlier version rewrote wrong figures in place. That was removed on purpose:
substituting a value into a sentence written to justify a different one produces
a confident falsehood, and it made true statements false
("a score of 80 or above is considered resilient" became "…50 or above…").
The reply is now **regenerated once**, and withheld in favour of a
ledger-built summary if it's still ungrounded.

Because the model never sees the profile, a turn with no `simulate` call has an
empty ledger — so a reply invented from nothing fails the check by default
rather than needing a special case.

`AgentLoop` takes its client by injection, so every agent test runs against a
scripted model — no network, no API key. The fake speaks the Responses API's
item shapes, including handing tool arguments back as a JSON *string*.
