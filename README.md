# ListingForge AI

**E-commerce conversion intelligence for Etsy sellers.** Not an AI writing tool — a system that models how buyers decide, maps their uncertainty, and builds every listing element to remove specific doubts.

## The Buyer Decision Engine (BDE)

The foundation of the platform. Every product is analyzed across six buyer decision stages:

| # | Stage | Buyer question |
|---|-------|----------------|
| 1 | attention | "Does anything here pull my eye?" (180px thumbnail, 40-tile grid) |
| 2 | interpretation | "What exactly is this, and what exactly do I get?" |
| 3 | trust | "Is this seller legitimate and is the quality real?" |
| 4 | usage_imagination | "Can I see this in my life?" |
| 5 | value_justification | "Is this worth the price vs my other open tabs?" |
| 6 | final_objection | "What could go wrong?" |

BDE output — `buyer_uncertainty_map`, `missing_information_gaps`, `trust_gaps`, `emotional_drivers`, `conversion_blockers`, `decision_friction_points` — feeds **every** downstream engine. Titles, description blocks, FAQ items, and all 7 image slots each declare the specific uncertainty they resolve.

## Pipeline

```
Input → Product Analysis → Buyer Decision Engine → Category Classification
      → Listing Strategy Engine → Image Strategy Engine (7 slots + prompts)
      → Output Formatter → UI
```

Hard rules, enforced at the Pydantic schema layer (see `backend/app/schemas.py`):
- Structured JSON between all modules (validated, with one automatic LLM repair pass)
- Exactly 7 image slots, each with intent / psychological_stage / purpose / structured prompt — aesthetic-only slots are **rejected by validation**
- All six BDE stages required or the output is rejected
- Exactly 13 Etsy tags, each ≤20 chars; titles ≤140 chars
- Category (`physical_product | digital_product | print_on_demand | gift_personalized | saas_tool`) drives the slot blueprint and description architecture


## Phase 2 — full pipeline enforcement

Enforced eight-step flow (orchestrator raises `PipelineError` and fails safe if any step is skipped or produces an invalid artifact):

```
1. Input ingestion + deterministic signal extraction   (pipeline/signals.py)
2. Product analysis
3. Buyer Decision Engine  → six named stage scores      (0.5·signals + 0.5·model)
4. Category classification → multi-signal, confidence-calibrated,
   conversion-relevance FALLBACK pass when confidence < 0.6
5. Listing strategy
6. Image strategy → IMAGE STRATEGY VALIDATOR            (pipeline/validator.py)
   auto-regenerates with precise feedback until valid (max 3 attempts)
7. Conversion Scoring Engine                            (pipeline/scoring.py)
8. Output Format Enforcer — final shape always contains:
   product_category, confidence, buyer_decision_engine, listing_strategy,
   image_prompts, validation_report, conversion_scores
```

**Validator rejection rules:** missing trust image · missing scale clarity ·
missing usage demonstration · any psychological stage covered by >2 slots ·
<4 distinct intents or <4 distinct visual types · duplicate/invalid uncertainty
mapping · incomplete prompt specs · unclaimed severity-5 image-resolvable doubts.

**Prompt hard requirements (schema-enforced):** every prompt carries subject,
lighting, camera, environment, composition, product_focus, realism_constraint;
overlays ≤6 words; rendered prompts end with the clause
*"Etsy conversion optimized, designed to reduce buyer uncertainty."*

**Conversion Scoring Engine:** CTR, trust, clarity, conversion, SEO, mobile,
and completeness — fully deterministic, each score built from signed
contributing factors with evidence, so identical inputs always score
identically and every number is auditable in the UI.

**Tests:** `python backend/tests/test_pipeline.py` — covers signal extraction,
score blending, every validator rule, the regenerate-until-valid loop, the
fail-safe path, scoring determinism, and final-shape enforcement. No API key
needed (LLM calls are mocked).

## Stack

- **Backend** — FastAPI + SQLAlchemy (SQLite dev / Postgres prod), JWT auth (bcrypt), file storage (local dev / S3-swappable), usage-metered billing with Stripe-ready checkout + webhooks
- **AI layer** — Anthropic API. Sonnet for reasoning stages, Haiku for classification. `pipeline/llm.py` enforces the JSON contract
- **Frontend** — React (Vite), no UI framework, custom design system. Served as static files by the API in production (single-service deploy)

## Run it

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000

# 2. Frontend (dev, hot reload — proxies /api to :8000)
cd frontend
npm install
npm run dev

# OR production single-service: build once, FastAPI serves it
cd frontend && npm run build
# then just run the backend — it mounts frontend/dist at /
```

Open the app, create an account (free tier: 3 generations/month), create a listing.

## Configuration

| Env var | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | required for generation | — |
| `DATABASE_URL` | Postgres in prod | sqlite:///./listingforge.db |
| `JWT_SECRET` | **set in prod** | dev value |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | enables paid checkout | off (quota still enforced) |
| `LF_STORAGE_DIR` | upload storage | ./storage |
| `LF_FREE_LISTINGS` / `LF_PRO_LISTINGS` | quota tuning | 3 / 100 |

## Production checklist

- [ ] Postgres via `DATABASE_URL`; run migrations with Alembic (models in `app/database.py`)
- [ ] Real `JWT_SECRET`; restrict CORS origin in `app/main.py`
- [ ] Stripe: create Pro/Scale prices, replace placeholder price IDs in `app/billing.py`, verify webhook signatures
- [ ] Swap `StorageBackend` for S3 (interface in `app/storage.py`)
- [ ] Move `_run_pipeline` from BackgroundTasks to a worker queue (Celery/RQ) at scale
- [ ] Rate-limit `/api/listings/generate`

## Repo layout

```
backend/app/
  schemas.py        ← the inter-module contracts + hard-rule validators
  pipeline/
    llm.py          ← structured-JSON LLM wrapper w/ repair pass
    product_analysis.py
    buyer_decision_engine.py   ← the core IP
    category_classifier.py
    listing_strategy.py
    image_strategy.py          ← 7-slot system + category blueprints
    output_formatter.py        ← Etsy paste-ready / CSV / image brief
    orchestrator.py
  routes/           ← auth, listings, billing
frontend/src/
  components/       ← Auth, Dashboard, NewListing, ListingDetail, Billing
```

## Phase 3 — Image Generation + Etsy Publishing + Analytics Loop

The pipeline now runs 11 enforced steps: the original 8, plus
`image_generation → image_validation → image_orchestration`.

### Image generation
- Provider abstraction (`app/imaging/providers.py`): `LocalStudioProvider`
  (deterministic Pillow renderer — real pixels, zero keys, used in dev/tests)
  and `FalProvider` (fal.ai FLUX for production).
- Every slot prompt carries lighting/camera/environment/composition specs and
  the mandatory suffix: *"Optimized for Etsy conversion. Designed to reduce
  buyer uncertainty and increase purchase confidence."*
- Pixel-level validation (`image_validator.py`): CTR effectiveness, trust,
  clarity (edge strength + Otsu bimodality), mobile visibility, thumbnail
  readability. Failures return concrete adjustments (contrast_boost,
  focal_strength, overlay_scale) and the engine regenerates up to 3× with
  escalation. Every attempt is logged to `image_generation_logs`; versions
  are kept in `listing_images` with a `superseded` flag.
- Orchestration sequences the 7 images into the psychological order:
  attention hero → interpretation → trust detail → scale → value →
  objection removal → brand reinforcement.

### Etsy publishing
- Full Etsy Open API v3 client (`app/etsy/client.py`): OAuth 2.0 PKCE,
  draft creation, ordered image upload (rank = psychological sequence),
  publish, stats, active-listing search. Injectable transport for tests.
- Blocking pre-publish gate: 7 images, CTR/trust/usage/scale coverage,
  valid taxonomy, exactly 13 tags.

### Self-improving loop
- `optimizer.sync_metrics` snapshots views/favorites per published listing;
  `performance_context` distills shop history and is injected into the Buyer
  Decision Engine on every new generation.
- Competitive analysis: keyword gaps, image-count gap, price positioning vs
  market median, plus an optional model pass for trust-signal diffs.

### Phase 3 environment variables
| Var | Purpose |
| --- | --- |
| `LF_IMAGE_PROVIDER` | `auto` (default), `local_studio`, or `fal` |
| `FAL_KEY` | fal.ai key — enables production image generation |
| `ETSY_API_KEY` | Etsy app keystring (OAuth client id) |
| `ETSY_REDIRECT_URI` | OAuth callback, e.g. `https://yourhost/api/etsy/callback` |

## Phase 4 — Premium UX, Workflows, Production Readiness

### Workspace
The dashboard is now a working surface: listing counts, live generation
progress bars (resumable from any device), shop performance (views, favorites,
favorite rate), deterministic AI recommendations ("2 drafts not yet on Etsy",
"listing X scores 54/100 — use the Editor"), plan usage, and a notifications
bell (generation complete/failed, publish results, low credits, batch done —
low-credit notices dedupe while unread).

### Guided generation with live progress
Every pipeline run reports its 11 steps through an `on_step` callback persisted
to `progress_json`, so the UI shows "step 7/11: image_generation" in real time
on the dashboard, the detail view, and bulk batches.

### Listing Editor + Live Quality Panel
`PATCH /api/listings/{id}` applies validated edits (title ≤140, exactly 13
unique tags ≤20 chars, price ≥ $0.20, materials ≤13) and immediately rescores.
The quality panel shows the 7 conversion scores plus two new ones:
**brand consistency** (measured pillar/voice/photography overlap with the
actual copy and prompts) and **compliance** (deterministic Etsy rule checks).
Every field has an **AI improve** button (`POST /{id}/assist`) that returns the
improved value *plus* the rationale and which buyer uncertainty it addresses.

### Image Studio
Etsy preview strip, mobile thumbnail mode, per-image conversion purpose and
psychological stage, ↑/↓ sequence reordering (server-validated permutation),
full version history with restore, and prompt editing — custom prompts get the
mandatory conversion suffix appended and still pass through pixel validation.

### Buyer Journey Simulator + SEO Studio
`GET /{id}/journey`: search-result appearance (desktop + mobile truncation),
image sequence with purposes, reading flow, 6-stage decision timeline, and
friction points (weak stages + unresolved high-severity doubts).
`GET /{id}/seo`: per-tag strength (length utilization, long-tail, buyer-intent
terms, title echo), title checks, and keyword suggestions mined from the
uncertainty map.

### Brand Studio
One brand system per account (voice, messaging pillars, photography style,
palette, packaging) injected into every generation alongside shop performance
history, with a one-click apply toggle and a consistency score on each listing.

### Bulk operations
`POST /api/workspace/bulk/generate` accepts up to 25 "title | description |
price" items, checks quota up front, runs the full pipeline per item in the
background with per-item progress, and notifies on completion.

### Exports
Per listing: JSON, CSV, Orvionix-styled PDF conversion report (reportlab), and
a ZIP asset package (copy + report + all 7 images + prompts).

### Accessibility & testing
Focus-visible outlines, aria labels/roles on interactive elements,
reduced-motion support. `tests/test_phase4.py` covers editor validation and
rescoring, brand consistency and context injection, compliance, SEO, journey,
exports, image reorder/versions/restore, notification dedupe, and pipeline
progress callbacks — 10 tests, alongside the Phase 2 and Phase 3 suites.

## Phase 5 (hardening slice) — Job Queue + Assist Metering

Deferred the intelligence upgrade until real usage data exists. Shipped now:

- **DB-backed job queue** (`app/jobs.py`, `jobs` table): single and bulk
  generation run through persistent jobs with 2 workers. On startup, stale
  `running` jobs are requeued — a server restart no longer strands work.
  Failed jobs retry once, then mark `failed` with the error.
- **AI assist metering**: each "AI improve" click is a real model call and is
  now quota'd at 5x the plan's monthly listing limit (free 15, pro 500),
  tracked in `listing_events`. Exceeding it returns 402.

Dormant Phase 5 foundations included (not yet wired into the pipeline):
`pipeline/context_manager.py`, `imaging/vision_analyzer.py`,
`imaging/quality_scorer.py`, plus schema for events/brand memory/flags —
ready for the intelligence phase once real listings exist.

## Photos-first intake

The New Listing flow is now a wizard, not a form:
1. **Drop product photos** — the vision engine reads palette, materials
   signals, sharpness, exposure, and background quality from the pixels, and
   flags photo issues the image strategy should compensate for.
2. **Answer only what pixels can't** — what it is (one line), digital or
   physical, price, optional must-know note.
3. **Brand branch** — existing brand system: one toggle. No brand configured:
   "Do you have an established brand?" Yes → three quick questions that create
   the Brand Studio profile (palette seeded from the photos). No → pure
   conversion mode.
4. **Generate** — the 11-step pipeline runs; measured photo analysis is
   injected into the Buyer Decision Engine alongside brand and performance
   context.

