# BreakPoint — Architecture Decisions

**Status:** Locked for Phase 1  
**Product:** BreakPoint (Financial Distress Simulator)  
**Last updated:** 2026-08-04  
**Repo root:** `breakpoint/`

---

## One-sentence product

BreakPoint stress-tests a person's finances against stacked emergencies and answers: **how many bad things can happen before severe financial risk?**

It is not a budgeting app. It finds the **breaking point**.

---

## The non-negotiable rule

> **The LLM talks. The simulation engine calculates. The database remembers. The frontend shows.**

Never let the model invent the resilience score, runway, or breaking point. Same inputs must always produce the same outputs (**deterministic**).

---

## Architecture we chose

### Decision

**Option 2: TypeScript frontend + Python backend**

```text
Supabase (Postgres + Auth)          ← profile + transcript, RLS per user
        ↕ 
Next.js (apps/web)
        ↓ HTTP / JSON
FastAPI (services/api)               ← stateless; never touches the database
        ↓
Pure Python simulation package
```

Persistence hangs off the web app, not the API. The simulation service stays
stateless: it is handed a profile and returns a result, which keeps the
deterministic guarantee easy to reason about and easy to test. See the
2026-08-12 rows in the decision log.

### Why not TypeScript-only?

TypeScript *can* run the calculator. We did not choose Python because month loops are “too hard” for TS.

We chose Python because:

1. **Simulation / risk modeling is the product differentiator**, not the form UI.
2. The project should demonstrate **ML / data-science** readiness (NumPy, SciPy, sklearn later).
3. Moving a tightly coupled TS calculator into Python later is expensive; adding FastAPI early is cheaper.
4. We can keep **one** Python backend — not a microservice zoo.

Tradeoff honesty: this is about **60/40**, not 90/10. We pay dual-stack cost today for modeling leverage later.

### What we explicitly rejected for now

| Temptation | Why wait |
|------------|----------|
| TypeScript simulation as source of truth | Wrong home for the differentiator + future ML |
| NumPy / Pandas / SciPy / sklearn on day one | Premature; plain Python loops first |
| LangGraph / multi-agent orchestra | After numbers are trustworthy |
| Plaid bank connection | Manual intake is the MVP wedge |
| Auth + Postgres on day one | Validate simulator first |
| Separate “simulation microservice” | One FastAPI app is enough |

---

## The three options we considered (summary)

| Option | Shape | Best when |
|--------|--------|-----------|
| **1. TS-only** | Next + TS engine | Ship polished MVP in ~3 weeks, ML maybe never |
| **2. Next + FastAPI** ← **chosen** | UI in TS, brain in Python | Simulation/ML is central to the story |
| **3. TS now, Python later** | Fast MVP, port later | Validate demand first; accept rewrite risk |

If priorities flip to “online in three weeks or die,” revisit Option 1/3 without shame.

---

## Monorepo layout

```text
breakpoint/                          ← git / project root
├── apps/
│   └── web/                         ← Next.js + TypeScript UI
│       ├── app/                     ← pages users see
│       ├── components/
│       │   ├── intake/              ← financial input UI
│       │   └── dashboard/           ← score / runway / results UI
│       ├── lib/
│       │   └── api/                 ← typed client that calls FastAPI
│       └── types/                   ← prefer GENERATED from OpenAPI
│
├── services/
│   └── api/                         ← FastAPI + simulation brain
│       ├── app/
│       │   ├── domain/              ← FinancialProfile, Scenario, Result
│       │   ├── simulation/          ← baseline, monthly loop, scoring, breaking point
│       │   ├── scenarios/           ← preset emergency library
│       │   ├── routes/              ← thin HTTP endpoints
│       │   └── main.py              ← (to be added)
│       └── tests/                   ← simulator tests (critical)
│
└── packages/
    └── contracts/                   ← shared OpenAPI / JSON Schema artifacts
```

### Boundary rules

| Layer | Allowed | Forbidden |
|-------|---------|-----------|
| `apps/web` | Forms, charts, call API, display results | Score formulas, month loops, shock math |
| `services/api` routes | Validate input, call simulation, return JSON | React, UI copy, LLM prompts (for now) |
| `domain` | Money / risk concepts as models | HTTP, DB, AI |
| `simulation` | Pure functions: inputs → outputs | Network calls, LLM, reading secrets mid-calc |

**Removed from the web app on purpose:** `lib/simulation`, `lib/scenarios`, `lib/scoring`. Those live under `services/api`.

---

## Contracts: language-agnostic JSON

The financial profile does **not** “belong” to TypeScript or Python. It is a **domain contract** represented as JSON.

### Principles

1. **Money in integer cents** — e.g. `435000` = $4,350.00 (avoid float bugs).
2. **`schemaVersion`** — so old saved profiles don’t silently break.
3. **One canonical schema** — do not hand-maintain two unrelated interfaces.
4. Nest by meaning (`income`, `expenses`, `debt`, `savings`), not one flat mega-form forever.

### Source of truth flow (Python owns schema)

```text
Pydantic models (Python)
        ↓
OpenAPI / JSON Schema
        ↓
Generated TypeScript types (apps/web/types)
```

Example shape (illustrative, not final):

```json
{
  "schemaVersion": 1,
  "currency": "USD",
  "income": {
    "monthlyTakeHomeCents": 435000
  },
  "expenses": {
    "rentCents": 155000,
    "utilitiesCents": 22000
  }
}
```

---

## Core product concepts (glossary)

| Term | Meaning |
|------|---------|
| **Baseline** | Normal month: income in, bills out, leftover |
| **Buffer / surplus** | Leftover after expenses |
| **Fixed expenses** | Rent, car, insurance, loan minimums |
| **Liquid savings** | Cash you can use quickly |
| **Emergency runway** | Months of essentials covered by savings |
| **Shock** | One emergency (repair, rent hike, missed paycheck) |
| **Stacked shocks** | Several emergencies in the same window |
| **Severe financial risk** | Can’t cover rent/essentials, or forced into dangerous debt |
| **Breaking point** | Smallest / most realistic combo that triggers severe risk |
| **Resilience score** | Explainable 0–100 from formulas, not vibes |
| **Deterministic** | Same inputs → same outputs every time |
| **Agent / LLM** | Asks questions, explains, plans — does not invent the score |
| **Guardrail** | Blocks dangerous advice (“take this loan”, “ignore medical bills”) |

---

## How pieces talk

```text
User fills intake form (web)
        ↓
POST /simulate with FinancialProfile JSON
        ↓
FastAPI validates with Pydantic
        ↓
Simulation engine runs scenarios (plain Python)
        ↓
Scoring + breaking-point search
        ↓
JSON result: score, runway, buffer, breaking point, scenario outcomes
        ↓
Dashboard renders (web)
```

Local dev (when scaffolded):

```text
Terminal 1: Next.js  → :3000
Terminal 2: FastAPI  → :8000
```

Frontend calls `http://localhost:8000`. CORS is a one-time setup, not a crisis.

---

## Build phases (do not skip order)

### Phase 1 — Manual deterministic simulator
- Intake form
- Python simulation engine
- Preset scenarios
- Resilience score + breaking point
- Dashboard
- **No LLM. No Plaid. Auth/DB optional.**

### Phase 2 — Agent explanation layer
- Conversational intake
- Plain-English explanation of *computed* results
- Action plan wording
- Guardrails

### Phase 3 — Real data context
- HUD Fair Market Rents, FRED, etc.
- Optional Plaid

### Phase 4 — Stickiness
- Score history, goals, “what changed,” risk alerts
- Heavier modeling / ML only if product pulls for it

### Phase 1 success criteria

1. User submits a profile  
2. Backend runs simulation  
3. UI shows score, runway, buffer, breaking point  
4. **Identical inputs → identical outputs**

---

## Python simulator discipline

Start with **plain Python functions**. Example spirit (not production code):

```text
each month:
  cash += income
  cash -= expenses
  cash -= shock costs
  if cash < 0 → debt spiral rules
```

Allowed later when justified: NumPy, SciPy, sklearn, notebooks.

Not day one: Pandas for the core loop, LangGraph, model training, distributed workers.

---

## Risks we already named

| Risk | Mitigation |
|------|------------|
| Financial advice liability | Educational framing; guardrails; no “take this loan / buy this stock” |
| Garbage-in accuracy | Show assumptions; cents; schema version |
| Privacy (esp. later Plaid) | Consent, minimal retention, delete path |
| Shame UX | “Fragile setup” not “you’re bad with money” |
| Dual-stack complexity | Thin routes, one contract, tests on the engine |

---

## Beachhead / wedge

First version positioning:

> **A financial fire drill for renters and new grads — especially before signing a lease.**

Narrow enough to build. Sharp enough to matter.

Killer line for the vision:

> A credit score tells institutions how risky you are to *them*. BreakPoint tells you how risky your life is to *you*.

---

## Next steps after this note

1. Design the canonical `FinancialProfile` JSON field-by-field.  
2. Scaffold FastAPI with `GET /health` only.  
3. Implement pure simulation + tests.  
4. Add `POST /simulate`.  
5. Wire Next intake → API → dashboard.  
6. Only then consider LLM explanation.

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-08-04 | Product = BreakPoint / financial distress simulator, not generic budget chatbot |
| 2026-08-04 | Deterministic engine owns numbers; LLM never invents score |
| 2026-08-04 | Stack = Next.js UI + FastAPI/Python simulation (Option 2) |
| 2026-08-04 | Monorepo: `apps/web`, `services/api`, `packages/contracts` |
| 2026-08-04 | Money as integer cents; `schemaVersion`; Pydantic → OpenAPI → generated TS types |
| 2026-08-04 | Phase 1 = manual form + simulator + dashboard; no Plaid/ML/agents yet |
| 2026-08-12 | Persistence = Supabase (Postgres + Auth), owned by `apps/web`, not `services/api` |
| 2026-08-12 | Profile stored as `jsonb`, not typed columns — pydantic stays the one canonical schema |
| 2026-08-12 | Sign-in optional; signed out the app is unchanged and nothing leaves the browser |
| 2026-08-12 | Email + password auth, not magic links — no SMTP dependency to sign in |
| 2026-08-12 | Web lookup supplies a *price* only; Python does every multiplication |
| 2026-08-12 | Looked-up values are proposals: shown with a citation, written only on user confirmation |
| 2026-08-12 | Lookup facts enter the grounding ledger, but the tool cannot mutate the profile |
