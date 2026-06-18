# SU Chatbot Onboarding Checklist

Use this **after SRKI acceptance tests pass consistently** (`python scripts/run_acceptance.py`).

## Phase 0 — Prerequisites

- [ ] SRKI acceptance suite at 100% (or agreed threshold)
- [ ] SRKI runbook validated on target machine
- [ ] SU dataset available: `E:\Final_SU_Dataset\SU_final_250k_A.json` (+ B if used)
- [ ] Official SU website seed URLs documented

## Phase 1 — Configuration isolation

- [ ] Add `ACTIVE_COLLEGE=SU` routing in [backend/app/config.py](../backend/app/config.py)
- [ ] Separate paths:
  - `su_dataset_a`, `su_dataset_b`
  - `su_intent_model_dir` → `models/su_intent`
  - `su_rag_index_dir` → `data/index/su`
  - `su_web_cache_dir` → `data/web_cache/su`
- [ ] SU web seed URLs (e.g. sarvajanikuniversity.ac.in pages)
- [ ] Ensure SRKI defaults unchanged when `ACTIVE_COLLEGE=SRKI`

## Phase 2 — Data pipeline

- [ ] `scripts/prepare_su_data.py` — merge SU JSON, export train/val
- [ ] `scripts/train_intent_su.py` — GPU training (DistilBERT/RoBERTa)
- [ ] `scripts/build_rag_index_su.py` — SU knowledge index (if applicable)
- [ ] `scripts/refresh_web_knowledge_su.py` — SU website scraper cache

## Phase 3 — Orchestrator routing

- [ ] College router selects SRKI vs SU orchestrator by `ACTIVE_COLLEGE` or request header
- [ ] SU intent label set mapped independently (SU intents ≠ SRKI intents)
- [ ] SU disambiguation map (if needed for SU-specific abbreviations)
- [ ] SU greeting / fallback copy

## Phase 4 — Evaluation

- [ ] `tests/acceptance_cases_su.py` — SU-specific acceptance cases
- [ ] `scripts/run_acceptance_su.py`
- [ ] Compare SRKI + SU reports in `data/reports/`
- [ ] Re-run SRKI suite after SU integration to confirm no regression

## Phase 5 — UI / API

- [ ] Optional college selector in [frontend/index.html](../frontend/index.html)
- [ ] Health endpoint shows active college + both cache statuses if multi-tenant
- [ ] README section for SU switch instructions

## Phase 6 — Deployment

- [ ] Separate `.env` profiles: `.env.srki`, `.env.su`
- [ ] Document GPU training time expectations for 250k SU dataset
- [ ] Schedule web cache refresh per college

## Estimated effort

| Task | Estimate |
|------|----------|
| Config + routing | 1–2 days |
| SU data prep + intent training | 3–7 days (GPU) |
| SU web scraper + acceptance | 2–3 days |
| UI selector + regression | 1–2 days |

## Notes

- Do **not** mix SRKI and SU intent labels in one classifier without explicit multi-label design.
- SU dataset is ~250k rows — use subset for dev, full set for final training.
- Keep SRKI and SU web caches separate to avoid cross-college answer contamination.
