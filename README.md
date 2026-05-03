# BearGrub

BearGrub is a UC Berkeley dining assistant. `apps/beargrub-ai/` is the active app. The other two directories are legacy projects preserved for reference.

## Architecture

```
User message (Chainlit)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                           app.py                              │
│  on_message()                                                 │
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
│    │                          ├─ YES → db.get()  (metadata)   │
│    │                          └─ NO  → similarity_search()    │
│    │                          sort_and_filter_chunks()        │
│    │                                                          │
│    └─ build_messages()                                        │
│         SYSTEM_PROMPT + retrieved context + history[-10:]     │
│              │                                                │
│              ▼                                                │
│         GPT (gpt-4o-mini) ◄─────────────────────────────┐    │
│              │           tools=MCP_TOOLS offered         │    │
│              │                                           │    │
│         stream chunks                                    │    │
│              │                                           │    │
│    ┌─────────┴──────────┐                                │    │
│    │                    │                                │    │
│  text token        tool_call:                            │    │
│  → Chainlit UI     get_menu                              │    │
│                         │                                │    │
│                    mcp_tools.py                          │    │
│                    handle_tool_call()                    │    │
│                    scraper → classifier → embed_menu()   │    │
│                         │                                │    │
│                    retrieve() on fresh db                │    │
│                         │                                │    │
│                    build_messages() + "menu refreshed"   │    │
│                         └────────────────────────────────┘    │
│                         (second GPT call, no tools)           │
└───────────────────────────────────────────────────────────────┘

Halal classification pipeline (classifier.py):
  classification_cache.json → deterministic rules → GPT fallback
```

### MCP tool: `get_menu`

`MCP_TOOLS` is passed as the `tools` parameter on every GPT call. GPT decides autonomously whether to invoke it based on this instruction in the tool description:

> "Only call if the user explicitly asks to refresh or if data seems incorrect for today."

In practice it fires in two scenarios:
1. **Explicit user request** — "refresh the menu", "reload", "update the menu"
2. **GPT self-correction** — GPT detects a mismatch between what the user describes and what the context shows, and judges a refresh is warranted

When invoked, the full scrape → classify → embed pipeline reruns and GPT gets a second completion with the fresh context. The second call passes `tools=None` to prevent recursive tool calls.

## Repository Layout

```
apps/
  beargrub-ai/         ← active app
    app.py             — Chainlit entrypoint, message routing, OpenAI streaming, PostHog telemetry
    scraper.py         — fetches Berkeley Dining XML menus for all halls
    classifier.py      — halal classification: cache → rules → GPT; writes classification_cache.json
    rag.py             — ChromaDB-backed vector store, InMemoryMenuStore fallback, smart retrieval
    mcp_tools.py       — MCP get_menu tool for autonomous live menu refresh
    prompts.py         — SYSTEM_PROMPT and CLASSIFICATION_PROMPT
    menu_answers.py    — legacy deterministic response builders (no longer used)
    tests/             — unit tests for all modules
  calinclusive-dining/ ← legacy Flask API
  halaliverse/         ← legacy Next.js frontend
```

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

## Legacy

`apps/calinclusive-dining/` — Flask API exposing `/api/halal-meals`, `/api/vegan-meals`, `/api/vegetarian-meals`.

`apps/halaliverse/` — Next.js frontend that consumed the Flask API. Expects it at `http://127.0.0.1:5000`.
