# SRKI Hybrid College Assistant

SRKI-only phase of the hybrid framework: preprocessing → intent recognition → pragmatic context → disambiguation → RAG → response.

**SU (Sarvajanik University) is intentionally disabled for now** — the same codebase can add `ACTIVE_COLLEGE=SU` and SU datasets in a later phase.

## Datasets (your paths)

| File | Records | Fields |
|------|---------|--------|
| `E:\Final_SRKI_dataset\Dataset_A_SRKI.json` | 22,000 | `text`, `intent` |
| `E:\Final_SRKI_dataset\Dataset_B_SRKI.json` | 22,000 | + `dialogue_act`, `context`, `ideal_response` |

## Quick start

```bash
cd "C:\Users\Shruti Revdiwala\Projects\college-hybrid-rag"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.env.example .env
```

### 1. Prepare data

```bash
python scripts/prepare_srki_data.py
```

### 2. Build RAG index (uses Dataset B + optional curriculum JSON)

```bash
python scripts/build_rag_index.py
```

### 3. Train intent model (GPU recommended)

```bash
python scripts/train_intent_srki.py
```

On a 2 GB GPU (e.g. MX450), training uses `fp16` and batch size 16. Full run is ~30–90 minutes depending on disk/GPU.

### 4. Run the app

```bash
python run.py
```

Open http://127.0.0.1:8001 (default port; use 8000 only if you change `port` in config)

If you see generic answers, you may still be hitting an **old server on port 8000** — stop it and use **8001**.

## API

- `GET /api/health` — intent + RAG + web cache readiness
- `POST /api/chat` — `{ "message": "...", "session_id": "optional" }`
- `POST /api/web/refresh` — re-scrape official SRKI pages

## Quality & regression

```bash
python scripts/run_acceptance.py      # 15-case acceptance suite (incl. multi-intent, VNSGU, unseen)
python scripts/validate_queries.py    # baseline validation report
```

Reports: `data/reports/acceptance_latest.json`, `data/reports/validation_baseline.json`

Runbook: [docs/RUNBOOK.md](docs/RUNBOOK.md)  
SU phase checklist: [docs/SU_ONBOARDING.md](docs/SU_ONBOARDING.md)

## Features

- Chat UI matching SRKI assistant mockups
- CS / BT / MB / IT disambiguation (e.g. “what is about CS?”)
- 11 SRKI intents from your dataset
- FAISS retrieval over `ideal_response` and curriculum JSON
- Keyword fallback until the DistilBERT model is trained

## Hybrid intelligence (multi-intent · unseen · web · anti-hallucination)

These map directly to the architecture diagrams (multi-intent detection, web/external
sources, reduced hallucination via grounding):

- **Multi-intent detection** — one query → several intents. Example: *"Tell me about
  admission process and fees structure"* returns a merged, per-intent answer.
  Detection is conservative (needs a conjunction/second question + 2 distinct intent
  groups) so simple questions stay single-intent.
- **Unseen / out-of-scope intents** — when no known intent matches (or model
  confidence is below `INTENT_CONFIDENCE_THRESHOLD`), the bot does **not** invent SRKI
  facts. It performs a grounded web search and clearly labels the result as unverified.
- **External institutions (VNSGU, Gujarat University, GTU, …)** — questions about any
  university other than SRKI are routed to a live web search (DuckDuckGo, no API key)
  and answered with **cited source links** plus a "not SRKI's own data — please verify"
  notice.
- **Anti-hallucination grounding** — answers come only from retrieved/curriculum/scraped
  context or cited web sources. The optional FLAN-T5 generator (`USE_GENERATOR=true`) is
  prompted to answer *only* from context and to say so when the answer isn't present.

Relevant config (in `.env` / `config.env.example`):

```
MULTI_INTENT_ENABLED=true
INTENT_CONFIDENCE_THRESHOLD=0.40
EXTERNAL_SEARCH_ENABLED=true
EXTERNAL_INSTITUTIONS=vnsgu,veer narmad,gtu,gujarat university,...
USE_GENERATOR=false            # set true to enable grounded FLAN-T5 generation
GENERATOR_MODEL=google/flan-t5-base
```

`GET /api/health` reports `multi_intent_enabled`, `external_search_enabled`, and
`generator_ready`. `/api/chat` responses include `intent`/`intents`, `source`
(`web` · `curriculum+web` · `rag+web` · `multi-intent` · `external_web` · `web_search`
· `fallback`), and `sources` when web results are used.

## Web scraping (latest official info)

Answers combine **local curriculum JSON**, **datasets**, and **scraped srki.ac.in pages** (admissions, contact, notices).

Refresh web cache manually:

```bash
python scripts/refresh_web_knowledge.py
```

Or while the API is running: `POST http://127.0.0.1:8001/api/web/refresh`

Cache is stored under `data/web_cache/` and refreshed automatically when older than 24 hours.

## Later: SU chatbot

Add `E:\Final_SU_Dataset\SU_final_250k_A.json`, a separate intent label set, and `ACTIVE_COLLEGE` routing — no need to rewrite the SRKI pipeline.
