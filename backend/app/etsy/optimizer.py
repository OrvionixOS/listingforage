"""
Automated Listing Optimizer + Competitive Advantage System.

OPTIMIZER (self-improving loop)
  sync_metrics(): pulls views/favorites for every published listing, stores
  snapshots, computes a favorite-rate CTR proxy.
  performance_context(): distills the user's historical results into a
  compact context block. The orchestrator injects it into the Buyer Decision
  Engine and Image Strategy prompts, so what actually performed feeds back
  into what gets generated next — the closed loop.

COMPETITIVE ADVANTAGE
  analyze(): pulls top active Etsy listings for the primary keyword and runs
  a deterministic diff (keyword gaps, image-count gaps, price positioning,
  tag overlap) plus a model pass for trust-signal comparison, producing
  optimization_recommendations.
"""
from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.orm import Session

from ..database import Listing, ListingImage, ListingMetric, PublishedListing
from ..schemas import ListingOutput
from .client import EtsyClient
from .publisher import _fresh_token

log = logging.getLogger("listingforge.optimizer")


# ---------------------------------------------------------------------------
# Metrics sync + feedback context
# ---------------------------------------------------------------------------

def sync_metrics(db: Session, conn, client: EtsyClient | None = None) -> int:
    client = client or EtsyClient()
    token = _fresh_token(db, conn, client)
    published = (db.query(PublishedListing)
                 .filter(PublishedListing.user_id == conn.user_id).all())
    n = 0
    for p in published:
        try:
            stats = client.get_listing_stats(token, p.etsy_listing_id)
        except Exception as exc:
            log.warning("stats fetch failed for %s: %s", p.etsy_listing_id, exc)
            continue
        views, favs = stats["views"], stats["favorites"]
        db.add(ListingMetric(
            published_listing_id=p.id, views=views, favorites=favs,
            ctr_proxy=(favs / views) if views else None, raw_json=stats["raw"]))
        n += 1
    db.commit()
    return n


def performance_context(db: Session, user_id: str, limit: int = 8) -> str:
    """Compact history of what worked, injected into future generations."""
    rows = (db.query(PublishedListing, ListingMetric, Listing)
            .join(ListingMetric, ListingMetric.published_listing_id == PublishedListing.id)
            .join(Listing, Listing.id == PublishedListing.listing_id)
            .filter(PublishedListing.user_id == user_id)
            .order_by(ListingMetric.captured_at.desc())
            .limit(limit * 4).all())
    if not rows:
        return ""
    seen: dict[str, tuple] = {}
    for pub, metric, listing in rows:  # latest snapshot per listing
        if pub.id not in seen:
            seen[pub.id] = (pub, metric, listing)
    ranked = sorted(seen.values(), key=lambda t: (t[1].ctr_proxy or 0), reverse=True)[:limit]
    lines = ["SHOP PERFORMANCE HISTORY (latest snapshots, best first):"]
    for pub, metric, listing in ranked:
        out = listing.output_json or {}
        cat = out.get("product_category", "?")
        title = (pub.payload_json or {}).get("title", listing.title)[:70]
        lines.append(
            f"- [{cat}] \"{title}\" -> views {metric.views}, favorites {metric.favorites}, "
            f"favorite-rate {round((metric.ctr_proxy or 0) * 100, 2)}%")
    lines.append("Weigh patterns from the highest favorite-rate listings when "
                 "choosing hooks, image emphasis, and title strategies.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Competitive Advantage System
# ---------------------------------------------------------------------------

def analyze(db: Session, listing: Listing, conn, client: EtsyClient | None = None,
            use_llm: bool = True) -> dict:
    client = client or EtsyClient()
    output = ListingOutput.model_validate(listing.output_json)
    token = _fresh_token(db, conn, client)
    keyword = output.listing_strategy.primary_keyword
    competitors = client.search_active_listings(token, keyword, limit=10)
    if not competitors:
        return {"keyword": keyword, "competitors_analyzed": 0,
                "optimization_recommendations": [
                    {"area": "keyword", "recommendation":
                     f"No active competitors returned for '{keyword}' — either a niche "
                     "opportunity or a non-buyer keyword; verify search volume."}]}

    recs: list[dict] = []

    # --- keyword gaps: terms competitors title-load that we don't -----------
    our_terms = set(" ".join([t.title.lower() for t in output.listing_strategy.titles]
                             + [t.lower() for t in output.listing_strategy.tags]).split())
    comp_counter: Counter = Counter()
    for c in competitors:
        for w in str(c.get("title", "")).lower().replace(",", " ").replace("|", " ").split():
            if len(w) > 3 and w.isalpha():
                comp_counter[w] += 1
    gaps = [w for w, n in comp_counter.most_common(30) if n >= 4 and w not in our_terms][:6]
    if gaps:
        recs.append({"area": "keyword_gaps",
                     "recommendation": f"Top competitors consistently use terms you don't: {', '.join(gaps)}. "
                                       "Test the relevant ones in tags or title variant B."})

    # --- image count gap ------------------------------------------------------
    our_images = (db.query(ListingImage)
                  .filter(ListingImage.listing_id == listing.id,
                          ListingImage.superseded.is_(False)).count())
    comp_img_counts = [len(c.get("images", []) or []) for c in competitors if c.get("images") is not None]
    if comp_img_counts:
        avg_imgs = sum(comp_img_counts) / len(comp_img_counts)
        if our_images < avg_imgs - 1:
            recs.append({"area": "image_gap",
                         "recommendation": f"Competitors average {avg_imgs:.0f} images; you have {our_images}. "
                                           "Regenerate any missing slots to complete the full 10-image gallery."})

    # --- price positioning -----------------------------------------------------
    prices = []
    for c in competitors:
        p = c.get("price") or {}
        try:
            prices.append(int(p.get("amount", 0)) / int(p.get("divisor", 100)))
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    if prices and listing.input_price:
        median = sorted(prices)[len(prices) // 2]
        ratio = listing.input_price / median if median else 1
        if ratio > 1.5:
            recs.append({"area": "pricing",
                         "recommendation": f"Your price ${listing.input_price:.2f} is {ratio:.1f}x the market median "
                                           f"(${median:.2f}). Premium pricing needs premium proof: strengthen slots 3 and 5 "
                                           "or add a value-stack image."})
        elif ratio < 0.6:
            recs.append({"area": "pricing",
                         "recommendation": f"Your price ${listing.input_price:.2f} is far under the median ${median:.2f} — "
                                           "under-pricing signals low quality on Etsy; test a raise with stronger value framing."})

    # --- trust-signal comparison (model pass) -----------------------------------
    if use_llm:
        try:
            from ..pipeline.llm import structured_call
            from pydantic import BaseModel

            class TrustDiff(BaseModel):
                weaker_trust_signals: list[str]
                missing_image_types: list[str]
                recommendations: list[str]

            comp_summary = "\n".join(
                f"- {str(c.get('title',''))[:90]}" for c in competitors[:8])
            diff, _ = structured_call(
                "You compare an Etsy listing against its top competitors and identify "
                "trust-signal weaknesses and missing image types. Be specific and actionable.",
                f"OUR LISTING TITLE: {output.listing_strategy.titles[0].title}\n"
                f"OUR IMAGE TYPES: {[s.required_visual_type for s in output.image_prompts.slots]}\n"
                f"OUR TRUST GAPS (self-identified): {[g.gap for g in output.buyer_decision_engine.trust_gap_analysis]}\n\n"
                f"TOP COMPETITOR TITLES:\n{comp_summary}",
                TrustDiff, max_tokens=1500, temperature=0.3)
            for r in diff.recommendations[:4]:
                recs.append({"area": "trust_signals", "recommendation": r})
            if diff.missing_image_types:
                recs.append({"area": "missing_image_types",
                             "recommendation": "Competitor sets include image types you lack: "
                                               + ", ".join(diff.missing_image_types[:5])})
        except Exception as exc:
            log.warning("competitive LLM pass skipped: %s", exc)

    return {"keyword": keyword, "competitors_analyzed": len(competitors),
            "optimization_recommendations": recs}
