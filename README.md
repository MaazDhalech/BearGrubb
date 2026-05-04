# BearGrub

BearGrub is a UC Berkeley dining assistant. `apps/beargrub-ai/` is the active app. The other two directories are legacy projects preserved for reference.

Live at: **http://44.222.246.112:8000**

## Architecture

```
User message (Chainlit)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                           app.py                              │
│  on_message()                                                 │
│    │                                                          │
│    ├─ Rate limit check (30 msg / 60s per session)             │
│    │                                                          │
│    ├─ Pre-context guard                                        │
│    │    └─ out-of-scope dates → return immediately            │
│    │                                                          │
│    ├─ ensure_fresh_menu()                                     │
│    │    └─ if stale/missing ──► scraper.py  fetch_all()       │
│    │                                │                         │
│    │                           classifier.py classify_all()   │
│    │                                │                         │
│    │                           rag.py  embed_menu()           │
│    │                                [ChromaDB / InMemory]     │
│    │                                                          │
│    ├─ retrieve() ──────────► rag.py                           │
│    │                          extract_filters()               │
│    │                          is_list_query()?                │
│    │                          ├─ YES → db.get()  (full menu)  │
│    │                          └─ NO  → similarity_search()    │
│    │                          sort_and_filter_chunks()        │
│    │                                                          │
│    └─ build_messages()                                        │
│         SYSTEM_PROMPT + retrieved context + history[-10:]     │
│              │                                                │
│              ▼                                                │
│         GPT-4o-mini ◄───────────────────────────────────┐    │
│              │           tools=MCP_TOOLS offered         │    │
│              │                                           │    │
│         stream chunks                                    │    │
│              │                                           │    │
│    ┌─────────┴──────────┐                                │    │
│    │                    │                                │    │
│  text token        tool_call:                            │    │
│  → Chainlit UI     get_menu                              │    │
│                         │                                │    │
│                    mcp_tools.py handle_tool_call()       │    │
│                    scraper → classifier → embed_menu()   │    │
│                         │                                │    │
│                    retrieve() on fresh db                │    │
│                         │                                │    │
│                    build_messages() + "menu refreshed"   │    │
│                         └────────────────────────────────┘    │
│                         (second GPT call, no tools)           │
└───────────────────────────────────────────────────────────────┘
```

### Halal classification pipeline (classifier.py)

Runs once per day at startup. Results cached in `classification_cache.json` — GPT only runs once per unique ingredient combination, never again.

```
Item from Berkeley XML
        │
        ├─ is_vegan? (Berkeley tag) ──► dietary_category = VEGAN, skip GPT
        │
        ├─ is_vegetarian? (Berkeley tag) ──► dietary_category = VEGETARIAN, skip GPT
        │
        └─ cache hit? ──► return cached result
                │
                └─ cache miss ──► GPT classifies ingredients
                                  │
                                  ├─ HALAL_MEAT  (meat confirmed halal)
                                  ├─ NOT_HALAL   (haram ingredient found)
                                  └─ UNCERTAIN   (ambiguous, e.g. unclear stock)
```

**Key rule:** unlabeled land meat defaults to `NOT_HALAL`. Seafood defaults to `HALAL`. When a user asks for "halal options", the LLM surfaces `HALAL_MEAT` items — not vegan/vegetarian items.

Each menu item is embedded into the vector store with its `Dietary Category`, `Halal Status`, nutrition data, and ingredients, so the LLM reasons directly from retrieved context.

### Example prompts

**"What halal meat options are at Crossroads for dinner?"**
- RAG retrieves top-20 Crossroads dinner chunks via cosine similarity
- LLM reads `Dietary Category: HALAL_MEAT` on each chunk, lists those only
- Shows halal disclaimer once per session

**"Build me a 2000 calorie meal, 150g protein"**
- RAG retrieves top-20 nutritionally relevant items
- LLM reasons over macros and builds a plan from available context
- No hardcoded logic — model picks combinations and explains tradeoffs

**"What's tomorrow's menu?"**
- Pre-context guard catches "tomorrow" before RAG runs
- Returns immediately: "I only have access to today's menu."
- Zero RAG calls, zero GPT cost

**"Refresh the menu"**
- GPT receives `MCP_TOOLS` and decides to call `get_menu`
- Full scrape → classify → embed pipeline reruns
- Second GPT call with fresh context, `tools=None` to prevent recursion

### MCP tool: `get_menu`

`MCP_TOOLS` is passed as the `tools` parameter on every GPT call. GPT decides autonomously whether to invoke it:

1. **Explicit user request** — "refresh the menu", "reload", "update the menu"
2. **GPT self-correction** — GPT detects a mismatch and judges a refresh is warranted

### Telemetry (PostHog)

Every message logs only safe metadata — no raw text ever leaves the app:
- `message_length`, `response_length` (lengths only)
- `halal_query` (boolean)
- `history_length`, `tool_call_count`
- Session ID (Chainlit-assigned, not user-identifying)

## Repository Layout

```
apps/
  beargrub-ai/               ← active app
    app.py                   — Chainlit entrypoint, message routing, OpenAI streaming, PostHog
    scraper.py               — fetches Berkeley Dining XML menus for all 4 halls
    classifier.py            — halal/vegan/vegetarian classification with GPT + caching
    rag.py                   — ChromaDB vector store, InMemoryMenuStore fallback, retrieval
    mcp_tools.py             — MCP get_menu tool for autonomous live menu refresh
    prompts.py               — SYSTEM_PROMPT and CLASSIFICATION_PROMPT
    menu_answers.py          — guardrails: out-of-scope date blocking, empty retrieval guard
    refresh.py               — standalone refresh CLI and RefreshSummary
    storage.py               — LocalMenuStorage and S3MenuStorage backends
    config.py                — env var loading
    classification_cache.json — committed warm cache so cold containers skip GPT
    tests/                   — 105 unit tests + offline prompt eval
  calinclusive-dining/       ← legacy Flask API
  halaliverse/               ← legacy Next.js frontend
docs/
  DEPLOYMENT.md              — ECS Fargate deployment runbook
  PHASE2_PLAN.md             — Phase 2 architecture plan
.github/workflows/
  beargrub-ai-ci.yml         — CI: compile + 105 unit tests + offline eval + secret guard
  beargrub-ai-deploy.yml     — Deploy: build → ECR push → ECS task update → redeploy
  beargrub-ai-live-eval.yml  — Live eval: 100-case GPT eval, manual + scheduled
```

## Deployment

Hosted on AWS ECS Fargate (us-east-1). Every push to `main` automatically:
1. Builds a `linux/amd64` Docker image
2. Pushes to Amazon ECR
3. Updates the ECS task definition
4. Redeploys the service with zero downtime

Required GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECS_CLUSTER`, `ECS_SERVICE`, `ECS_TASK_DEFINITION`.

## Local Setup

```bash
cd apps/beargrub-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `apps/beargrub-ai/.env`. `POSTHOG_API_KEY` is optional.

```bash
.venv/bin/chainlit run app.py
```

Run tests:

```bash
cd apps/beargrub-ai && .venv/bin/python -m pytest tests/ -v
```

Run the offline prompt eval used by CI:

```bash
cd apps/beargrub-ai && .venv/bin/python tests/offline_prompt_eval.py
```

Refresh today's menu data from the command line:

```bash
cd apps/beargrub-ai && .venv/bin/python refresh.py --date "$(date +%F)" --hall ALL --json
```

## Legacy

`apps/calinclusive-dining/` — Flask API exposing `/api/halal-meals`, `/api/vegan-meals`, `/api/vegetarian-meals`.

`apps/halaliverse/` — Next.js frontend that consumed the Flask API. Expects it at `http://127.0.0.1:5000`.
