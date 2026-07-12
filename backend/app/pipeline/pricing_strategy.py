"""
Stage 7 — Pricing Strategy Engine.

Recommends a single price point plus the full monetization picture: charm/
psychological pricing rationale, bundle opportunities, upsells, and premium
version ideas — grounded in the product's category, value density, the Buyer
Decision Engine's value-justification findings, and (when the Competitor
Intelligence Engine fetched one) the MEASURED live-market price distribution
for this exact keyword.
"""
from __future__ import annotations

from ..schemas import (BDEOutput, CategoryClassification, CompetitorIntelligence,
                       PricingStrategy, ProductAnalysis)
from .llm import structured_call

SYSTEM = """You are the Pricing Strategy Engine of Etsy Listing AI Studio — an
ecommerce strategist specializing in Etsy digital-product pricing psychology.

RULES:
- recommended_price must be a realistic Etsy digital-product price for this
  category and value density (typically $2-$45 for single items, higher for
  large bundles). Never guess wildly — anchor to price_tier and
  competitive_context from the product analysis.
- IF LIVE MARKET PRICES ARE PROVIDED, they are measured from the actual top
  Etsy results for this keyword right now. Position recommended_price
  relative to the measured median deliberately (undercut, match, or premium)
  and say which move you're making and why in psychological_pricing_note.
  price_range_low/high should sit inside or near the measured range unless
  you explicitly justify pricing outside it.
- Use charm pricing ($X.99 / $X.49 / round-number premium framing) and explain
  WHY in psychological_pricing_note — reference anchoring, decoy effects, or
  round-number premium perception as appropriate.
- price_range_low/high must bracket recommended_price and reflect realistic
  category variance.
- price_positioning: state budget | mid-market | premium AND why, grounded in
  the BDE's value_justification_score and emotional drivers.
- bundle_opportunities: concrete bundle ideas that pair THIS product with
  adjacent products in the same category (name specific complementary items).
- upsell_ideas: concrete post-purchase or listing-level upsells (commercial
  license upgrade, extra formats, editable source files, matching set).
- premium_version_opportunities: how a higher-tier version of THIS exact
  product could be built and priced, and what buyer segment it serves."""


def _market_prices_block(intel: CompetitorIntelligence | None) -> str:
    snap = (intel.market_snapshot or {}) if intel is not None else {}
    if not snap.get("listings_analyzed") or snap.get("price_median") is None:
        return ("NO LIVE MARKET PRICES AVAILABLE — anchor to the product "
                "analysis price tier; do not fabricate measured numbers.")
    return (f"LIVE MARKET PRICES — top {snap['listings_analyzed']} active Etsy "
            f"listings for \"{snap.get('keyword', '')}\" (measured now): "
            f"range ${snap['price_min']:.2f}-${snap['price_max']:.2f}, "
            f"median ${snap['price_median']:.2f}.")


def run(analysis: ProductAnalysis, bde: BDEOutput,
        classification: CategoryClassification,
        competitor_intel: CompetitorIntelligence | None = None) -> tuple[PricingStrategy, dict]:
    content = (
        f"PRODUCT ANALYSIS:\n{analysis.model_dump_json(indent=1)}\n\n"
        f"CATEGORY: {classification.category.value}\n"
        f"VALUE JUSTIFICATION SCORE: {bde.scores.value_justification_score}/100\n"
        f"EMOTIONAL DRIVERS: {', '.join(bde.emotional_drivers)}\n"
        f"DOMINANT PURCHASE SCENARIO: {bde.dominant_purchase_scenario}\n\n"
        f"{_market_prices_block(competitor_intel)}\n\n"
        "Produce the complete pricing strategy for this product."
    )
    return structured_call(SYSTEM, content, PricingStrategy,
                           max_tokens=2500, temperature=0.4)
