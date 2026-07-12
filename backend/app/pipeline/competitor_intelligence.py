"""
Stage 6 — Competitor Intelligence Engine.

Models the current Etsy marketplace for this digital product category and
produces a concrete plan for beating it.

GROUNDING: when ETSY_API_KEY is configured, the engine first runs a live
Etsy search for the listing's primary keyword (public-scope API — no shop
connection needed) and reduces the top results to a deterministic
MarketSnapshot: real price distribution, real title language, real tag
usage, real favorite counts. The model is instructed to treat that snapshot
as ground truth and cite it. Without a key (or on any fetch failure) the
engine degrades to category-convention reasoning and labels the output
data_source="model_knowledge" so the UI never presents modeled patterns as
measured ones.
"""
from __future__ import annotations

from ..etsy.market_research import MarketSnapshot, fetch_market_snapshot
from ..schemas import (BDEOutput, CategoryClassification, CompetitorIntelligence,
                       ListingStrategy, ProductAnalysis)
from .llm import structured_call

SYSTEM = """You are the Competitor Intelligence Engine of Etsy Listing AI
Studio — an ecommerce strategist and market researcher who has studied
thousands of Etsy digital-product listings in this category. You model the
current competitive landscape and produce a concrete plan for beating it.

Ground every claim in evidence — be specific to the category and product,
never generic ("good SEO helps sales" is banned; "competitors bury file
formats in paragraph 3 — lead with a formats line in the first 200
characters" is the bar).

IF LIVE ETSY MARKET DATA IS PROVIDED, it is measured from the actual top
search results for this keyword RIGHT NOW. It outranks your general
knowledge wherever the two disagree:
- pricing_patterns MUST use the measured price range and median.
- popular_keywords MUST be drawn from the measured title terms and tags
  (you may add close variants a buyer would also type).
- best_selling_patterns and competitor_weaknesses MUST reference what the
  sample titles actually do and fail to do — quote or paraphrase them.
- missed_opportunities: things NONE of the sampled listings cover that this
  product can claim first.
If no live data is provided, reason from category conventions and never
present a modeled number as a measured one.

Cover:
- best_selling_patterns: what top sellers in this category actually do
  (title structure, image count/style, bundling, pricing anchors).
- popular_keywords: search terms buyers in this category actually use.
- common_image_styles: the visual conventions competitors default to.
- pricing_patterns: where prices cluster and why (with actual $ context for
  this product's tier).
- customer_expectations: what buyers assume they'll get in this category.
- review_language_signals: phrases buyers commonly praise or complain about
  for this category (e.g. "instant access", "confusing instructions").
- competitor_weaknesses: concrete, specific gaps — not "could be better".
- missed_opportunities: gaps competitors leave open that THIS listing can
  claim first.
- advantages: at least 3, each naming one area (positioning | seo | imagery |
  value_perception | buyer_communication) and exactly how THIS listing's
  strategy wins there, referencing this product's actual analysis and BDE
  findings."""


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification,
        listing: ListingStrategy,
        snapshot: MarketSnapshot | None = None) -> tuple[CompetitorIntelligence, dict]:
    """`snapshot` is injectable for tests; by default a live fetch runs here."""
    if snapshot is None:
        snapshot = fetch_market_snapshot(listing.primary_keyword)

    market_block = snapshot.render() if snapshot.ok else (
        "NO LIVE MARKET DATA AVAILABLE"
        + (f" ({snapshot.error})" if snapshot.error else "")
        + " — reason from category conventions; do not fabricate measured numbers.")

    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"CATEGORY: {classification.category.value}\n"
        f"CATEGORY REASONING: {classification.reasoning}\n\n"
        f"DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}\n"
        f"EMOTIONAL DRIVERS: {', '.join(bde.emotional_drivers)}\n"
        f"TOP CONVERSION BLOCKERS: {', '.join(bde.conversion_blockers)}\n\n"
        f"THIS LISTING'S PRIMARY KEYWORD: {listing.primary_keyword}\n"
        f"THIS LISTING'S TAGS: {', '.join(listing.tags)}\n"
        f"THIS LISTING'S PRICE ANCHOR STRATEGY: {listing.price_anchor_strategy}\n\n"
        f"{market_block}\n\n"
        "Produce the complete competitor intelligence report for this product."
    )
    result, usage = structured_call(SYSTEM, content, CompetitorIntelligence,
                                    max_tokens=5000, temperature=0.5)
    # provenance is set here, from what actually happened — never model-claimed
    result.data_source = "live_etsy_data" if snapshot.ok else "model_knowledge"
    result.market_snapshot = snapshot.to_dict()
    return result, usage
