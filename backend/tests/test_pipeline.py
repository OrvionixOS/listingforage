"""
Etsy Listing AI Studio — pipeline test suite (no API key required).

Covers:
  - deterministic signal extraction
  - BDE score computation (signal + model blend)
  - validator rejection rules and feedback
  - orchestrator auto-regeneration loop (invalid first attempt → valid second)
  - conversion scoring determinism
  - final output format enforcement
Run:  python -m pytest tests/ -q   (or python tests/test_pipeline.py)
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[0].parent))

from app import schemas as S
from app.pipeline import signals, validator, scoring
from app.pipeline.buyer_decision_engine import compute_scores


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def make_analysis() -> S.ProductAnalysis:
    return S.ProductAnalysis(
        product_name="Liquid Gold Foil Digital Paper Pack",
        core_offer="12 seamless liquid-gold metallic texture files, instant download.",
        materials_or_format=["JPG", "12x12 in", "300 DPI"],
        key_attributes=["seamless tiling", "foil look", "commercial use"],
        target_buyer="Wedding stationery designers needing premium gold backgrounds.",
        who_buys_and_why="Wedding stationery designers who need premium gold backgrounds "
                         "fast, because commissioning custom textures is slow and expensive.",
        buying_occasion="Business use for client invitation suites.",
        seasonality="Peaks in engagement/wedding-planning season (Nov-Mar).",
        price_tier="mid",
        competitive_context="Hundreds of gold papers; most repeat visibly when tiled.",
        market_positioning="Mid-tier bundle vs single-texture budget listings.",
        emotional_buying_triggers=["Wants client work to look expensive", "Time pressure before a deadline"],
        ambiguities=["No tiling proof", "License unstated", "PNG availability unclear"],
    )


def make_bde() -> S.BDEOutput:
    sa = S.StageAssessment
    model = S.BDEModelOutput(
        stage_assessments=[
            sa(stage="attention", buyer_question="Does anything pull my eye?", current_answer_strength=6,
               risks=["Gold papers look identical at 180px"]),
            sa(stage="interpretation", buyer_question="What exactly do I get?", current_answer_strength=4,
               risks=["Digital vs physical ambiguity"]),
            sa(stage="trust", buyer_question="Is the quality real?", current_answer_strength=3,
               risks=["No zoom proof"]),
            sa(stage="usage_imagination", buyer_question="Can I see this in my work?", current_answer_strength=5),
            sa(stage="value_justification", buyer_question="Worth it vs other tabs?", current_answer_strength=5),
            sa(stage="final_objection", buyer_question="What could go wrong?", current_answer_strength=2,
               risks=["License fear"]),
        ],
        buyer_uncertainty_map=[
            S.UncertaintyItem(stage="interpretation", uncertainty="Is this a digital file or a shipped product?", severity=5, resolvable_by=["image", "title"]),
            S.UncertaintyItem(stage="final_objection", uncertainty="Can I legally use these in client work I sell?", severity=5, resolvable_by=["image", "faq"]),
            S.UncertaintyItem(stage="trust", uncertainty="Will these look pixelated printed large?", severity=4, resolvable_by=["image"]),
            S.UncertaintyItem(stage="interpretation", uncertainty="Do the textures tile seamlessly?", severity=4, resolvable_by=["image"]),
            S.UncertaintyItem(stage="value_justification", uncertainty="How different are the 12 textures?", severity=3, resolvable_by=["image"]),
            S.UncertaintyItem(stage="usage_imagination", uncertainty="Would these suit an elegant wedding suite?", severity=3, resolvable_by=["image"]),
            S.UncertaintyItem(stage="attention", uncertainty="Is this pack distinct from cheaper lookalikes?", severity=3, resolvable_by=["image"]),
            S.UncertaintyItem(stage="usage_imagination", uncertainty="Could these work for branding beyond weddings?", severity=2, resolvable_by=["image"]),
            S.UncertaintyItem(stage="interpretation", uncertainty="What exact file formats are included?", severity=4, resolvable_by=["image", "description"]),
            S.UncertaintyItem(stage="final_objection", uncertainty="Which apps/software will open these files?", severity=3, resolvable_by=["image", "faq"]),
        ],
        missing_information_gaps=["License", "PNG availability"],
        trust_gap_analysis=[
            S.TrustGap(gap="No print-quality proof", evidence="No zoom crop, only full-frame previews",
                       severity=4, remedy="100% zoom crop with DPI callout"),
            S.TrustGap(gap="Seamlessness claimed, not shown", evidence="Copy says seamless with no tiled demo",
                       severity=4, remedy="3x3 tiling demonstration image"),
        ],
        emotional_drivers=["Wants client work to look expensive", "Relief of not designing from scratch"],
        conversion_blockers=["License uncertainty", "Digital-vs-physical ambiguity"],
        decision_friction_points=["Specs require reading full description"],
        dominant_purchase_scenario="Stationery designer sourcing a premium gold background for a client wedding suite, deciding in 90 seconds.",
    )
    sig = signals.extract(
        "Liquid Gold Foil Digital Paper, 12 seamless textures instant download",
        "12 JPG files, 12x12 in, 300 DPI. Commercial use included. Perfect for wedding invitations.",
        8.99, 4)
    return S.BDEOutput(**model.model_dump(), scores=compute_scores(model, sig),
                       input_signals=sig.to_dict())


def make_prompt(subject: str, overlays=None) -> S.ImagePrompt:
    return S.ImagePrompt(
        subject=subject,
        lighting="large softbox 45 degrees camera-left, soft specular highlights",
        camera="100mm macro lens, f/5.6, 15-degree top-down angle",
        environment="honed black slate surface, seamless charcoal backdrop",
        composition="single dominant focal point, rule of thirds, generous negative space",
        product_focus="the gold texture fills 85 percent of frame and stays the hero",
        realism_constraint="honest material rendering, true metallic behavior, no CGI plasticity",
        text_overlays=overlays or [],
        negative="flat texture, banding, oversaturation",
    )


def make_slot(sid, intent, stage, objective, vtype, primary) -> S.ImageSlot:
    return S.ImageSlot(
        slot_id=sid, role=S.IMAGE_ROLE_BY_SLOT[sid], intent=intent, psychological_stage=stage,
        objective=objective, required_visual_type=vtype,
        prompt_constraints=["legible at 180px", "no stock-render look"],
        prompt=make_prompt(f"gold texture scene for slot {sid}"),
        primary_uncertainty_id=primary,
    )


def make_valid_strategy() -> S.ImageStrategy:
    return S.ImageStrategy(slots=[
        make_slot(1, "CTR", "attention", "Distinct from cheaper lookalike gold papers at thumbnail scale", "hero_macro", 6),
        make_slot(2, "CLARITY", "interpretation", "Kills digital-vs-physical doubt: shows exactly what files arrive", "file_grid", 0),
        make_slot(3, "VALUE", "value_justification", "Shows how different the 12 textures are, justifying pack price", "variant_grid", 4),
        make_slot(4, "CONTEXT", "usage_imagination", "Shows textures suiting an elegant wedding suite in real client work", "mockup_in_use", 5),
        make_slot(5, "CONTEXT", "usage_imagination", "Shows these working for branding beyond weddings", "lifestyle_scene", 7),
        make_slot(6, "TRUST", "trust", "Proves print quality at 100 percent zoom, no pixelation", "zoom_proof", 2),
        make_slot(7, "CLARITY", "interpretation", "Demonstrates the textures tile seamlessly with no repeat lines", "tiling_demo", 3),
        make_slot(8, "CLARITY", "interpretation", "Shows exact file formats included", "info_card", 8),
        make_slot(9, "VALUE", "value_justification", "Shows the finished-project transformation these enable", "comparison_split", 9),
        make_slot(10, "CONVERSION", "final_objection", "Removes the commercial license blocker for business buyers", "info_card", 1),
    ])


def make_invalid_strategy() -> S.ImageStrategy:
    """Structurally legal (passes schema) but must FAIL the validator:
    no trust proof, no usage demo, over-covered stage, low diversity."""
    def slot(sid, primary):
        return make_slot(sid, "CLARITY", "interpretation",
                         f"Generic clarity objective number {sid} about the files",
                         "hero_macro", primary)
    slots = [slot(i, i - 1) for i in range(1, 10)]
    slots.append(make_slot(10, "CTR", "attention",
                           "Another attention-grab visual for the search grid",
                           "hero_macro", 9))
    return S.ImageStrategy(slots=slots)


def make_listing() -> S.ListingStrategy:
    return S.ListingStrategy(
        primary_keyword="gold foil digital paper",
        secondary_keywords=["metallic texture", "wedding background"],
        long_tail_keywords=["gold foil digital paper for wedding invitations"],
        search_phrases=["seamless gold texture instant download"],
        titles=[
            S.TitleVariant(title="Gold Foil Digital Paper — 12 Seamless Metallic Textures, 300 DPI Instant Download, Commercial Use", strategy="Resolves both severity-5 doubts in-title.", is_best=True),
            S.TitleVariant(title="Liquid Gold Texture Pack, Luxury Digital Paper for Wedding Invitations, 12x12 Instant Download", strategy="Emotional driver: luxury client work."),
            S.TitleVariant(title="Seamless Gold Foil Backgrounds, 12 Printable Metallic Papers, 300 DPI JPG, Small Business License", strategy="Differentiator: seamless claim."),
            S.TitleVariant(title="Gold Digital Paper Bundle, 12 Metallic Backgrounds for Branding & Stationery, Instant Download", strategy="SEO-maximal phrasing."),
            S.TitleVariant(title="Luxury Gold Foil Textures for Wedding Designers, 12 Files, Commercial License Included", strategy="Benefit-led phrasing."),
            S.TitleVariant(title="12 Gold Foil Digital Papers, Seamless Tileable Metallic Textures, 300 DPI, Instant Download", strategy="Spec-forward phrasing."),
        ],
        title_explanation="The best title front-loads the primary keyword and resolves both severity-5 doubts (digital-vs-physical, commercial license) in the visible 40-char window.",
        tags=["gold digital paper", "gold foil texture", "metallic background",
              "seamless pattern", "wedding stationery", "digital download",
              "commercial use", "luxury scrapbook", "gold backdrop",
              "invitation paper", "printable paper", "junk journal gold",
              "branding texture"],
        materials=["JPG file", "300 DPI"],
        description_blocks=[
            S.DescriptionBlock(section="opening_hook", heading="What you get", bde_stage="interpretation",
                body="12 seamless gold foil textures — JPG, 12x12 in, 300 DPI. Instant digital download; nothing ships.",
                uncertainty_resolved="Digital vs physical ambiguity"),
            S.DescriptionBlock(section="file_details", heading="Print-perfect quality", bde_stage="trust",
                body="Every file is 3600x3600 px. Zoom to 100% and the foil detail stays crisp.",
                uncertainty_resolved="Pixelation-when-printed doubt"),
            S.DescriptionBlock(section="transformation", heading="Made for client work", bde_stage="usage_imagination",
                body="Drop these behind invitation suites, brand mockups, or packaging.",
                uncertainty_resolved="Elegant wedding aesthetic fit"),
            S.DescriptionBlock(section="objection_handling", heading="Commercial license included", bde_stage="final_objection",
                body="Unlimited client projects; products for sale up to 500 units per design.",
                uncertainty_resolved="Can I legally use these in work I sell"),
        ],
        price_anchor_strategy="Per-texture math: 12 textures under $0.75 each vs $15+ single stock licenses.",
        faq_items=[
            {"question": "Can I use these in products I sell?",
             "answer": "Yes — commercial license covers client work and items for sale.",
             "blocker_resolved": "Commercial license uncertainty"},
        ],
    )


def make_competitor_intel() -> S.CompetitorIntelligence:
    return S.CompetitorIntelligence(
        best_selling_patterns=["Top bundles show per-item math in the value image",
                               "Top listings lead titles with the file count"],
        popular_keywords=["gold digital paper", "wedding stationery texture"],
        common_image_styles=["flat-lay grid", "styled mockup"],
        pricing_patterns="Bundles of 10-15 textures cluster at $6-$12.",
        customer_expectations=["Seamless tiling proof", "Commercial license stated up front"],
        review_language_signals=["praise: 'exactly as pictured'", "complaint: 'no license info'"],
        competitor_weaknesses=["Most listings bury the license terms in paragraph 3",
                               "Few show a 100% zoom crop proving resolution"],
        missed_opportunities=["No competitor shows a branding use case beyond weddings",
                              "No competitor shows a tiling demo image"],
        advantages=[
            S.CompetitorAdvantage(area="seo", how_this_listing_wins="License terms front-loaded in tags and first description line."),
            S.CompetitorAdvantage(area="imagery", how_this_listing_wins="Dedicated tiling-demo and zoom-proof slots competitors skip."),
            S.CompetitorAdvantage(area="value_perception", how_this_listing_wins="Per-texture cost math shown directly in the value-breakdown image."),
        ],
    )


def make_pricing() -> S.PricingStrategy:
    return S.PricingStrategy(
        recommended_price=8.99, price_range_low=6.99, price_range_high=12.99,
        psychological_pricing_note="Charm pricing at $8.99 anchors below the $9-$10 bundle cluster.",
        price_positioning="mid-market — premium finish, bundle-tier quantity.",
        bundle_opportunities=["Pair with a matching rose-gold texture pack"],
        upsell_ideas=["Extended commercial license upgrade", "PNG transparent variant add-on"],
        premium_version_opportunities=["A 30-texture 'deluxe' tier at a higher price point"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_signal_extraction():
    s = signals.extract(
        "Gold Foil Digital Bundle 12 Files Instant Download",
        "12 JPG files, 12x12 in, 300 DPI. Commercial use bundle pack of 12. Perfect for invitations. FAQ below.",
        8.99, 5, ["texture_01.jpg", "texture_02.jpg"])
    assert s.spec_hits >= 3, s.spec_hits
    assert s.category_hits["digital_bundle"] > s.category_hits["pattern"]
    assert "jpg" in s.detected_formats
    assert 0 <= s.interpretation_signal <= 100
    empty = signals.extract("thing", "nice item", None, 0)
    assert empty.interpretation_signal < s.interpretation_signal
    print("PASS signal extraction")


def test_score_blend():
    bde = make_bde()
    sc = bde.scores
    # trust: model 3/10 → blend must sit between heuristic and 30
    assert 0 <= sc.trust_score <= 100
    assert sc.objection_score < sc.attention_score  # weakest model stage stays weakest-ish
    print("PASS score blend:", sc.model_dump())


def test_validator_rejects_and_feeds_back():
    bde = make_bde()
    ok, checks, feedback = validator.validate(make_invalid_strategy(), bde)
    assert not ok
    failed = {c.check for c in checks if not c.passed}
    assert "trust_image_present" in failed
    assert "usage_demonstration_present" in failed
    assert "no_duplicate_stage_coverage" in failed
    assert "slot_diversity" in failed
    assert feedback, "must emit regeneration feedback"
    print(f"PASS validator rejection ({len(failed)} rules tripped, {len(feedback)} feedback items)")


def test_validator_accepts_valid():
    bde = make_bde()
    ok, checks, feedback = validator.validate(make_valid_strategy(), bde)
    assert ok, [c.detail for c in checks if not c.passed]
    print("PASS validator acceptance (all", len(checks), "checks green)")




def test_prompt_render_contains_clause():
    p = make_prompt("test subject for the render check")
    r = p.render()
    for req in ["LIGHTING:", "CAMERA:", "ENVIRONMENT:", "COMPOSITION:",
                "PRODUCT FOCUS:", "REALISM:", S.CONVERSION_CLAUSE]:
        assert req in r, req
    try:
        S.ImagePrompt(subject="x", lighting="", camera="", environment="",
                      composition="", product_focus="", realism_constraint="")
        raise AssertionError("vague prompt must be rejected")
    except ValueError:
        pass
    print("PASS prompt hard requirements + conversion clause")


def test_scoring_deterministic_and_explained():
    bde, listing, images = make_bde(), make_listing(), make_valid_strategy()
    report = validator.build_report(True, [], 1, [])
    a = scoring.compute(bde, listing, images, report)
    b = scoring.compute(bde, listing, images, report)
    assert a == b, "scoring must be deterministic"
    for name, cs in a.model_dump().items():
        assert 0 <= cs["score"] <= 100
        assert cs["explanation"]
        assert len(cs["contributing_factors"]) >= 2, name
    print("PASS scoring:", {k: v["score"] for k, v in a.model_dump().items()})


def test_orchestrator_regeneration_loop():
    """First image attempt invalid → validator feedback → second attempt valid."""
    from app.pipeline import orchestrator

    analysis, bde, listing = make_analysis(), make_bde(), make_listing()
    competitor_intel, pricing = make_competitor_intel(), make_pricing()
    attempts = {"n": 0}

    def fake_image_run(a, b, c, regeneration_feedback=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            assert regeneration_feedback is None
            return make_invalid_strategy(), {"tokens_in": 10, "tokens_out": 10}
        assert regeneration_feedback, "second attempt must receive validator feedback"
        return make_valid_strategy(), {"tokens_in": 10, "tokens_out": 10}

    with patch.object(orchestrator.product_analysis, "run",
                      lambda *a, **k: (analysis, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.buyer_decision_engine, "run",
                      lambda *a, **k: (bde, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.category_classifier, "run",
                      lambda *a, **k: (S.CategoryClassification(
                          category="digital_bundle", confidence=0.95,
                          reasoning="digital texture files, instant download",
                          signals_considered=["lexical", "structural", "BDE scenario"],
                          listing_structure_implications=["download disambiguation", "license visuals",
                                                          "file grid slot", "spec-first description"]),
                          {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.listing_strategy, "run",
                      lambda *a, **k: (listing, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.competitor_intelligence, "run",
                      lambda *a, **k: (competitor_intel, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.pricing_strategy, "run",
                      lambda *a, **k: (pricing, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.image_strategy, "run", fake_image_run):
        result = orchestrator.generate_listing("Gold Foil Paper", "12 textures")

    assert attempts["n"] == 2
    assert result.output.validation_report.valid
    assert result.output.validation_report.attempts == 2
    assert result.output.validation_report.regeneration_feedback
    assert result.stage_log == list(orchestrator.PIPELINE_STEPS)
    dumped = result.output.model_dump()
    for k in S.FINAL_OUTPUT_REQUIRED_KEYS:
        assert k in dumped and dumped[k] is not None, k
    print("PASS orchestrator regeneration loop + format enforcement")
    return result


def test_fail_safe_when_never_valid():
    from app.pipeline import orchestrator
    analysis, bde, listing = make_analysis(), make_bde(), make_listing()
    competitor_intel, pricing = make_competitor_intel(), make_pricing()

    with patch.object(orchestrator.product_analysis, "run",
                      lambda *a, **k: (analysis, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.buyer_decision_engine, "run",
                      lambda *a, **k: (bde, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.category_classifier, "run",
                      lambda *a, **k: (S.CategoryClassification(
                          category="digital_bundle", confidence=0.9, reasoning="r",
                          listing_structure_implications=["a", "b", "c", "d"]),
                          {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.listing_strategy, "run",
                      lambda *a, **k: (listing, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.competitor_intelligence, "run",
                      lambda *a, **k: (competitor_intel, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.pricing_strategy, "run",
                      lambda *a, **k: (pricing, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.image_strategy, "run",
                      lambda *a, **k: (make_invalid_strategy(),
                                       {"tokens_in": 1, "tokens_out": 1})):
        try:
            orchestrator.generate_listing("x title", "y description")
            raise AssertionError("must fail safe")
        except orchestrator.PipelineError as e:
            assert e.step == "image_strategy_validated"
            print("PASS fail-safe:", str(e)[:90])


if __name__ == "__main__":
    test_signal_extraction()
    test_score_blend()
    test_validator_rejects_and_feeds_back()
    test_validator_accepts_valid()
    test_prompt_render_contains_clause()
    test_scoring_deterministic_and_explained()
    result = test_orchestrator_regeneration_loop()
    test_fail_safe_when_never_valid()
    print("\nALL TESTS PASSED")
    # Persist the mocked result for UI seeding
    import json, pathlib
    pathlib.Path("/tmp/demo_output.json").write_text(
        json.dumps(result.output.model_dump(mode="json")))
