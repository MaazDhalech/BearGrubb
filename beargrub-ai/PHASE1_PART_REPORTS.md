# Phase 1 Part Reports

## Part 1 - Scraper

### What was built
- Added `config.py` with dining hall IDs, endpoint, local paths, model names, and environment loading.
- Added `scraper.py` with `fetch_all(date, hall='ALL')`, Berkeley dining menu URL construction, XML parsing, JSON-wrapped XML support, nutrient extraction, vegan/vegetarian dietary tag parsing, allergen parsing, and `calories_per_oz` precomputation.
- Added scraper tests covering field extraction, small serving sizes, all-hall fetch behavior, single-hall URL construction, and fetch-failure continuation.

### Deviations from the spec and why
- Added JSON-wrapped XML support in `parse_response_content()` because the specified endpoint is under `wp-json` even though the payload structure is XML. This keeps the parser compatible with either response envelope.
- Did not create `.env` with placeholder secrets. A real `.env` should be local-only; the code reads env vars and requirements will document expected names.

### Updated vulnerability log
- External dining menu fetches can fail or return malformed data. Mitigation: scraper logs errors and returns no items for that hall instead of crashing.
- The Berkeley endpoint is unauthenticated remote input. Mitigation: parser extracts only known XML fields into plain dictionaries and does not execute content.
- No secrets are written to disk by this part.

### Next part
- Build `classifier.py` with persisted cache, ingredient normalization, deterministic halal rules, shellfish handling, empty-ingredient handling, and GPT fallback plumbing.

## Part 2 - Classifier

### What was built
- Added `classifier.py` with `load_cache()`, `save_cache()`, `normalize()`, `get_cache_key()`, deterministic halal classification, shellfish detection, GPT fallback, result coercion, and `classify_all()`.
- Added an empty local `classification_cache.json` for persisted cache shape.
- Added classifier tests covering more than 10 specified cases: halal-labeled meat, unlabeled meat, alcohol, vanilla extract, shellfish, gelatin, halal gelatin, empty ingredients, natural flavors, single-ingredient produce, and ignoring halal labels outside ingredients.
- Added tests for normalized cache keys, cache persistence, GPT fallback plumbing, and `classify_all()` enrichment.

### Deviations from the spec and why
- Expanded deterministic classification beyond the spec's Step 3 so obviously safe vegetarian/produce items return `HALAL` without spending an OpenAI call. This is consistent with the edge case that salad bar single-ingredient items should be halal.
- Preserved semicolon-aware ingredient segment checks by splitting the original ingredient string first, then normalizing each segment. The spec says normalize before matching but also says to split normalized text on semicolons; stripping punctuation would remove semicolons, so this implementation keeps both requirements working.
- If OpenAI is unavailable for a GPT-review item, the classifier returns `UNCERTAIN` instead of crashing. This keeps the local app usable and matches the spec's uncertainty behavior.
- Kept `CLASSIFICATION_PROMPT` in `classifier.py` for this part; Part 5 will move prompt constants to `prompts.py`.

### Updated vulnerability log
- Ingredient strings are untrusted remote content. Mitigation: deterministic rules operate on normalized plain text and GPT calls send ingredients only as user content under a strict JSON-only system prompt.
- Cache poisoning risk exists if `classification_cache.json` is manually edited. Mitigation: cached and GPT results are coerced to known statuses and shellfish fields before use.
- OpenAI dependency/API absence can break classification. Mitigation: GPT-review cases degrade to `UNCERTAIN` when the client/package is unavailable.
- No API keys are hardcoded.

### Next part
- Build `rag.py` with structured filter extraction before retrieval, document/metadata construction, ChromaDB embedding when dependencies are installed, a local in-memory fallback for tests, and staleness detection.
