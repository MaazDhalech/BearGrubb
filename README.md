# BearGrub

BearGrub contains three UC Berkeley dining projects:

- `apps/beargrub-ai/` - the current Phase 1 Chainlit dining assistant with scraper, halal classification, RAG retrieval, MCP refresh support, PostHog telemetry, and tests.
- `apps/calinclusive-dining/` - the legacy Flask API and data scripts for halal, vegan, and vegetarian meal endpoints.
- `apps/halaliverse/` - the legacy Next.js frontend for browsing halal, vegetarian, and vegan options.

## Repository Layout

```text
apps/
  beargrub-ai/
    app.py
    scraper.py
    classifier.py
    rag.py
    mcp_tools.py
    prompts.py
    tests/
  calinclusive-dining/
    app.py
    MealClassification.py
    generate_data.py
    archive/
    test-json/
  halaliverse/
    app/
    package.json
```

## BearGrub AI

BearGrub AI is the active app. It uses Python, Chainlit, OpenAI, LangChain, and ChromaDB.

### Local Setup

```bash
cd apps/beargrub-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `apps/beargrub-ai/.env`. `POSTHOG_API_KEY` is optional for local testing.

Run the assistant:

```bash
chainlit run app.py -w
```

Run tests from the repository root:

```bash
python3 -m unittest discover -s apps/beargrub-ai/tests -v
```

## Legacy Flask API

The legacy Flask backend is preserved in `apps/calinclusive-dining/`.

```bash
cd apps/calinclusive-dining
python3 -m venv .venv
source .venv/bin/activate
pip install flask flask-cors requests openai
python app.py
```

The API listens on `http://127.0.0.1:5000` and exposes:

- `GET /api/halal-meals`
- `GET /api/vegan-meals`
- `GET /api/vegetarian-meals`

## Legacy Next.js Frontend

The legacy frontend is preserved in `apps/halaliverse/`.

```bash
cd apps/halaliverse
npm install
npm run dev
```

Visit `http://localhost:3000`. It expects the legacy Flask API at `http://127.0.0.1:5000`.
