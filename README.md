# Etsy Listing AI Studio

**A fully automated AI Etsy listing engine for DIGITAL PRODUCTS.** A creator uploads product files; the platform acts as an Etsy SEO specialist, ecommerce strategist, conversion copywriter, product photographer, graphic designer, brand strategist, market researcher, and customer psychology expert — and hands back a complete, Etsy-ready launch package. No Etsy knowledge, SEO knowledge, copywriting skill, marketing skill, or design skill required from the creator.

This is not an AI writing tool — it's a system that models how digital-product buyers decide, maps their uncertainty, and builds every listing element (titles, tags, description, pricing, competitor positioning, and all 10 gallery images) to remove specific doubts.

## Digital Product Category Engine

The platform recognizes and optimizes for eight Etsy digital product categories, each with its own selling strategy, image blueprint, and description architecture:

| Category | Examples | What's optimized |
|---|---|---|
| `printable_art` | Wall art, nursery prints, quote prints, gallery walls | Room placement, interior style, size guides, decor keywords |
| `digital_planner` | Budget/wedding/fitness/productivity planners | Organization benefits, time-saving, lifestyle transformation |
| `template` | Canva/business/resume/social-media templates | Professional outcomes, time saved, ease of customization |
| `invitation` | Wedding/birthday/event invitations | Occasion, personalization, event emotion |
| `svg_cut_file` | Cricut/Silhouette/laser cut files | Software compatibility, craft usage, included formats |
| `digital_bundle` | Clipart bundles, design packs, mega collections | Perceived value, quantity, bundle savings |
| `educational_product` | Worksheets, flashcards, learning resources | Parent/teacher benefits, learning outcomes |
| `pattern` | Sewing/crochet/knitting patterns | Skill level, materials, finished result |

Category is auto-detected from a multi-signal classifier (lexical term hits, structural signals, detected file formats, and the Buyer Decision Engine's dominant purchase scenario) and drives the image blueprint and description architecture end to end.

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

BDE output — `buyer_uncertainty_map` (10+ distinct doubts), `missing_information_gaps`, `trust_gaps`, `emotional_drivers`, `conversion_blockers`, `decision_friction_points` — feeds **every** downstream engine. Titles, description blocks, FAQ items, and all 10 image slots each declare the specific uncertainty they resolve.

## Pipeline

```
Input → Product Analysis (incl. "who buys this and why")
      → Buyer Decision Engine → Digital Product Category Classification
      → Listing Strategy Engine (titles, SEO, description architecture)
      → Competitor Intelligence Engine → Pricing Strategy Engine
      → Image Strategy Engine (10 slots + prompts) → Output Formatter → UI
```

Hard rules, enforced at the Pydantic schema layer (see `backend/app/schemas.py`):
- Structured JSON between all modules (validated, with one automatic LLM repair pass)
- Exactly 10 image slots — the complete Etsy gallery — each with a FIXED conversion role plus intent / psychological_stage / purpose / structured prompt — aesthetic-only slots are **rejected by validation**
- All six BDE stages required, and at least 10 distinct buyer uncertainties (one per image slot), or the output is rejected
- Exactly 6 titles (best + 5 alternatives) and exactly 13 Etsy tags, each ≤20 chars; titles ≤140 chars
- Category (`printable_art | digital_planner | template | invitation | svg_cut_file | digital_bundle | educational_product | pattern`) drives the slot blueprint and description architecture

### The 10-image Etsy gallery

Every slot has a fixed conversion role, in this exact order:

| # | Role | Purpose |
|---|------|---------|
| 1 | Hero | Click-optimized search thumbnail |
| 2 | Overview | Exactly what's included |
| 3 | Value breakdown | Quantity/features, per-item math |
| 4 | Lifestyle mockup | Ownership in a real setting |
| 5 | Alternate use case | A second way to use it |
| 6 | Close-up detail | Quality proof at 100% zoom |
| 7 | How it works | Step-by-step usage |
| 8 | Sizes/formats/compatibility | Exact specs, required software |
| 9 | Benefits/transformation | The before/after outcome |
| 10 | Brand + CTA | License terms, brand reinforcement, call to action |

## Competitor Intelligence Engine — grounded in live Etsy data

At generation time, the engine runs a **real Etsy search** for the listing's primary keyword (`etsy/market_research.py`, public-scope API — needs only `ETSY_API_KEY`, no shop OAuth) and reduces the top 25 active listings to a deterministic **MarketSnapshot**: measured price range/median, terms the top titles converge on (with counts), most-used tags, average favorites, and sample competing titles. That snapshot is injected into the model prompt as ground truth — pricing patterns must use the measured numbers, popular keywords must come from the measured terms, weaknesses must reference what the sampled titles actually do — and stored on the output so every claim is auditable.

The result covers best-selling patterns, popular keywords, common image styles, pricing patterns, customer expectations, review language, competitor weaknesses, missed opportunities, and a concrete "how this listing beats competitors" plan across positioning, SEO, imagery, value perception, and buyer communication (`pipeline/competitor_intelligence.py`).

**Provenance is engine-enforced:** `data_source` is set to `live_etsy_data` or `model_knowledge` from what actually happened (never model-claimed), and the UI labels each. No API key, a network failure, or an empty result set degrades to category-convention reasoning — it never kills the pipeline and never presents modeled numbers as measured ones.

## Pricing Strategy Engine

Recommends a price point with psychological-pricing rationale, plus bundle opportunities, upsell ideas, and premium-version opportunities — grounded in the product's category, value density, the BDE's value-justification findings, and the **measured live-market price distribution** from the Competitor Intelligence step: the model must position the price deliberately against the real median (undercut, match, or premium) and say which move it's making (`pipeline/pricing_strategy.py`).

## Full pipeline enforcement

Enforced flow (orchestrator raises `PipelineError` and fails safe if any step is skipped or produces an invalid artifact):

```
1. Input ingestion + deterministic signal extraction   (pipeline/signals.py)
2. Product analysis (incl. who-buys-and-why, detected file formats)
3. Buyer Decision Engine  → six named stage scores      (0.5·signals + 0.5·model)
4. Digital Product Category classification → multi-signal, confidence-calibrated,
   conversion-relevance FALLBACK pass when confidence < 0.6
5. Listing strategy (titles, SEO package, 11-section description architecture)
6. Competitor Intelligence Engine
7. Pricing Strategy Engine
8. Image strategy (10 slots) → IMAGE STRATEGY VALIDATOR (pipeline/validator.py)
   auto-regenerates with precise feedback until valid (max 3 attempts)
9. Conversion Scoring Engine                            (pipeline/scoring.py)
10. Output Format Enforcer — final shape always contains:
    product_category, confidence, buyer_decision_engine, listing_strategy,
    image_prompts, competitor_intelligence, pricing_strategy,
    validation_report, conversion_scores
```

With a DB session, three more steps generate the actual 10 gallery images, pixel-validate them, and sequence them: `image_generation → image_validation → image_orchestration`.

**Validator rejection rules:** missing trust image · missing scale/what's-included clarity · fewer than 2 usage demonstrations · any psychological stage covered by >3 of the 10 slots · <5 distinct intents or <6 distinct visual types · duplicate/invalid uncertainty mapping · incomplete prompt specs · unclaimed severity-5 image-resolvable doubts.

**Prompt hard requirements (schema-enforced):** every prompt carries subject, lighting, camera, environment, composition, product_focus, realism_constraint; overlays ≤6 words; rendered prompts end with the clause *"Etsy conversion optimized, designed to reduce buyer uncertainty."*

**Conversion Scoring Engine:** CTR, trust, clarity, conversion, SEO, mobile, and completeness — fully deterministic, each score built from signed contributing factors with evidence, so identical inputs always score identically and every number is auditable in the UI.

**Tests:** `python backend/tests/test_pipeline.py` — covers signal extraction, score blending, every validator rule, the regenerate-until-valid loop, the fail-safe path, scoring determinism, and final-shape enforcement. No API key needed (LLM calls are mocked).

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
| `LF_ALLOWED_ORIGIN` | CORS origin in prod | https://app.etsylistingaistudio.com |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | enables paid checkout | off (quota still enforced) |
| `LF_STORAGE_DIR` | upload storage | ./storage |
| `LF_FREE_LISTINGS` / `LF_PRO_LISTINGS` | quota tuning | 3 / 100 |
| `LF_IMAGE_PROVIDER` | `auto` (default), `local_studio`, or `fal` |
| `FAL_KEY` | fal.ai key — enables production image generation |
| `ETSY_API_KEY` | Etsy app keystring — enables live market research at generation time AND shop OAuth publishing |
| `ETSY_REDIRECT_URI` | OAuth callback, e.g. `https://yourhost/api/etsy/callback` |

## Production checklist

- [ ] Postgres via `DATABASE_URL`; run migrations with Alembic (models in `app/database.py`)
- [ ] Real `JWT_SECRET`; set `LF_ALLOWED_ORIGIN` to your production origin
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
    buyer_decision_engine.py       ← the core IP
    category_classifier.py        ← Digital Product Category Engine
    listing_strategy.py           ← titles, SEO package, description architecture
    competitor_intelligence.py    ← Competitor Intelligence Engine
    pricing_strategy.py           ← Pricing Strategy Engine
    image_strategy.py             ← 10-slot system + category blueprints
    output_formatter.py           ← Etsy paste-ready / CSV / image brief
    orchestrator.py
  routes/           ← auth, listings, billing
frontend/src/
  components/       ← Auth, Dashboard, NewListing, ListingDetail, Billing
```

## Image generation

- Provider abstraction (`app/imaging/providers.py`): `LocalStudioProvider` (deterministic Pillow renderer — real pixels, zero keys, used in dev/tests) and `FalProvider` (fal.ai FLUX for production).
- Every slot prompt carries lighting/camera/environment/composition specs and the mandatory suffix: *"Optimized for Etsy conversion. Designed to reduce buyer uncertainty and increase purchase confidence."*
- Pixel-level validation (`image_validator.py`): CTR effectiveness, trust, clarity (edge strength + Otsu bimodality), mobile visibility, thumbnail readability. Failures return concrete adjustments (contrast_boost, focal_strength, overlay_scale) and the engine regenerates up to 3× with escalation. Every attempt is logged to `image_generation_logs`; versions are kept in `listing_images` with a `superseded` flag.
- Orchestration is deterministic: display order = slot_id order, since each slot already carries a fixed conversion role (hero → overview → value breakdown → lifestyle mockup → alternate use case → close-up detail → how it works → sizes/formats/compatibility → benefits/transformation → brand+CTA).

## Etsy publishing

- Full Etsy Open API v3 client (`app/etsy/client.py`): OAuth 2.0 PKCE, draft creation, ordered image upload (rank = gallery sequence), publish, stats, active-listing search. Injectable transport for tests.
- Blocking pre-publish gate: all 10 images, CTR/trust/usage/scale coverage, valid taxonomy, exactly 13 tags.
- Every listing is a digital download (`type=download`, `is_digital=True`, quantity uncapped) — there is no physical-fulfillment branch.

## Self-improving loop

- `optimizer.sync_metrics` snapshots views/favorites per published listing; `performance_context` distills shop history and is injected into the Buyer Decision Engine on every new generation.
- Live competitive analysis (`GET /etsy/{id}/competitive`): keyword gaps, image-count gap, price positioning vs market median against actual active Etsy listings, distinct from the pre-generation Competitor Intelligence Engine above.

## Workspace, editor, and studio

- **Workspace** — listing counts, live generation progress bars (resumable from any device), shop performance, deterministic AI recommendations, plan usage, and a notifications bell.
- **Listing Editor + Live Quality Panel** — `PATCH /api/listings/{id}` applies validated edits (title ≤140, exactly 13 unique tags ≤20 chars, price ≥ $0.20, materials ≤13) and immediately rescores. The quality panel shows the 7 conversion scores plus **brand consistency** and **compliance**. Every field has an **AI improve** button (`POST /{id}/assist`) returning the improved value, rationale, and which buyer uncertainty it addresses.
- **Image Studio** — Etsy preview strip, mobile thumbnail mode, per-image conversion purpose and psychological stage, ↑/↓ sequence reordering, full version history with restore, and prompt editing.
- **Buyer Journey Simulator + SEO Studio** — `GET /{id}/journey` (search-result appearance, 10-image sequence with purposes, reading flow, 6-stage decision timeline, friction points) and `GET /{id}/seo` (per-tag strength, title checks, keyword suggestions).
- **Market intel tab** — Competitor Intelligence Engine output ("how this listing beats competitors") and Pricing Strategy Engine output (recommended price, bundles, upsells, premium tiers) in one place.
- **Brand Studio** — one brand system per account (voice, messaging pillars, photography style, palette, packaging) injected into every generation, with a consistency score on each listing.
- **Bulk operations** — `POST /api/workspace/bulk/generate` accepts up to 25 items, checks quota up front, runs the full pipeline per item in the background with per-item progress.
- **Exports** — per listing: JSON, CSV, PDF conversion + market-intelligence report, and a ZIP asset package (copy + report + all 10 images + prompts + competitor/pricing briefs).
- **Job queue** — single and bulk generation run through a DB-backed job queue (`app/jobs.py`) with 2 workers; stale `running` jobs are requeued on restart; failed jobs retry once.

## Digital-only intake

The New Listing flow is a wizard, not a form:
1. **Drop product files** — the vision engine reads palette, materials signals, sharpness, exposure, and background quality from the pixels, and flags photo issues the image strategy should compensate for.
2. **Answer only what pixels can't** — what it is (one line), price, optional must-know note. Every product on this platform is a digital download.
3. **Brand branch** — existing brand system: one toggle. No brand configured: three quick questions create the Brand Studio profile (palette seeded from the photos), or skip for pure conversion mode.
4. **Generate** — the full pipeline runs; measured photo analysis is injected into the Buyer Decision Engine alongside brand and performance context.
