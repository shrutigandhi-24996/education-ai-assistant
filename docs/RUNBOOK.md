# SRKI Hybrid Assistant — Runbook

## Start the application

```bash
cd "C:\Users\Shruti Revdiwala\Projects\college-hybrid-rag"
.venv\Scripts\activate
python run.py
```

- Default URL: **http://127.0.0.1:8001**
- Health check: **http://127.0.0.1:8001/api/health**

Expected health fields:

| Field | Healthy value |
|-------|----------------|
| `status` | `ok` |
| `curriculum_files` | `62` (or similar) |
| `web_cache_pages` | `> 0` |
| `web_cache_fresh` | `true` (within 24h of refresh) |

## Refresh web knowledge (official srki.ac.in)

```bash
python scripts/refresh_web_knowledge.py
```

Or via API (server running):

```bash
curl -X POST http://127.0.0.1:8001/api/web/refresh
```

Cache location: `data/web_cache/srki_web_cache.json`

## Run acceptance regression suite

```bash
python scripts/run_acceptance.py
```

Report: `data/reports/acceptance_latest.json`

Exit code `0` = all cases passed.

## Troubleshooting

### ERR_CONNECTION_REFUSED

1. Server not running — start with `python run.py`
2. Wrong port — default is **8001** (not 8000)
3. Check: `netstat -ano | findstr :8001`

### Generic / weak answers

1. Refresh web cache: `python scripts/refresh_web_knowledge.py`
2. Check health: `web_cache_pages` should be > 0
3. For semester syllabus, include program + sem (e.g. `sem-3 course details of MB`)

### Stale admission / fee info

- Web cache TTL is 24 hours (config: `WEB_CACHE_TTL_HOURS`)
- Force refresh before demos or after website updates

### Intent model not ready

- Keyword fallback is used until you train:
  ```bash
  python scripts/prepare_srki_data.py
  python scripts/train_intent_srki.py
  ```

## Optional: RAG index

```bash
python scripts/build_rag_index.py
```

## Stop the server

Press `Ctrl+C` in the terminal running `python run.py`.

If port stuck, end the Python process using that port from Task Manager.
