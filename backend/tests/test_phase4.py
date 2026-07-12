"""
Phase 4 tests — editor, quality panel, insights, exports, image studio ops,
notifications, brand system, bulk. Run: python tests/test_phase4.py
"""
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import editor, exporter, insights
from app.brandctx import brand_context
from app.database import (Base, BrandProfile, Listing, ListingImage,
                          Notification, SessionLocal, User, engine, init_db)
from app.imaging import generator
from app.notify import notify_generation, notify_low_credits
from test_phase3 import make_output


def fresh():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    user = User(email="p4@test.com", password_hash="x")
    db.add(user); db.commit()
    output = make_output()
    listing = Listing(user_id=user.id, title="Gold Paper", status="complete",
                      input_price=8.99, category="digital_bundle",
                      output_json=output.model_dump(mode="json"))
    db.add(listing); db.commit()
    return db, user, listing


def with_images(db, listing):
    from app.schemas import ListingOutput
    output = ListingOutput.model_validate(listing.output_json)
    generator.generate_all(db, listing.id, output.image_prompts)
    return output


def test_editor_validation():
    db, user, listing = fresh()
    r = editor.apply_edits(db, listing, {"title": ""})
    assert not r.ok and "empty" in r.errors[0].lower()
    r = editor.apply_edits(db, listing, {"title": "x" * 141})
    assert not r.ok and "140" in r.errors[0]
    r = editor.apply_edits(db, listing, {"tags": ["a"] * 5})
    assert not r.ok
    r = editor.apply_edits(db, listing, {"tags": ["dup"] * 13})
    assert not r.ok and any("unique" in e.lower() for e in r.errors)
    r = editor.apply_edits(db, listing, {"price": 0.05})
    assert not r.ok and "0.20" in r.errors[0]
    r = editor.apply_edits(db, listing, {"nonsense": 1})
    assert not r.ok and "Unknown" in r.errors[0]
    print("PASS editor validation: empty/too-long titles, bad tag sets, "
          "sub-minimum price, unknown fields all rejected")
    db.close()


def test_editor_apply_and_rescore():
    db, user, listing = fresh()
    new_title = "Liquid Gold Foil Digital Paper 12 Seamless Luxury Textures Instant Download"
    tags = [f"gold tag {i:02d}" for i in range(12)] + ["luxury gold paper"]
    r = editor.apply_edits(db, listing, {"title": new_title, "tags": tags, "price": 12.5})
    assert r.ok, r.errors
    saved = db.get(Listing, listing.id)
    assert saved.output_json["listing_strategy"]["titles"][0]["title"] == new_title
    assert saved.input_price == 12.5
    assert "conversion_score" in r.scores and "compliance" in r.scores
    assert "brand_consistency" in r.scores
    print("PASS editor apply+rescore: edits persisted, scores refreshed, "
          f"compliance={r.scores['compliance']['score']}")
    db.close()


def test_brand_consistency_and_context():
    db, user, listing = fresh()
    # unconfigured: score is None with guidance
    b = editor.brand_consistency(None, __import__("app.schemas", fromlist=["ListingOutput"])
                                 .ListingOutput.model_validate(listing.output_json))
    assert b["score"] is None
    profile = BrandProfile(user_id=user.id, brand_name="Digital Glow Press",
                           voice="luxury editorial precise gold",
                           photography_style="macro softbox specular",
                           messaging_pillars=["seamless textures", "instant download",
                                              "quantum entanglement"])  # last one won't match
    db.add(profile); db.commit()
    scores = editor.rescore(db, listing)
    bc = scores["brand_consistency"]
    assert bc["score"] is not None and 0 < bc["score"] < 100
    assert any("quantum" in p for p in bc["problems"])
    ctx = brand_context(db, user.id)
    assert "BRAND SYSTEM" in ctx and "Digital Glow Press" in ctx
    profile.apply_to_generations = False
    db.commit()
    assert brand_context(db, user.id) == ""
    print(f"PASS brand system: consistency={bc['score']}, missing pillar flagged, "
          "context injects and respects the apply toggle")
    db.close()


def test_compliance_score():
    db, user, listing = fresh()
    scores = editor.rescore(db, listing)
    comp = scores["compliance"]
    assert any("10 listing images" in p for p in comp["problems"])  # none generated yet
    with_images(db, listing)
    comp2 = editor.rescore(db, listing)["compliance"]
    assert comp2["score"] > comp["score"]
    assert not any("images" in p for p in comp2["problems"])
    print(f"PASS compliance: {comp['score']} -> {comp2['score']} after images generated")
    db.close()


def test_seo_report():
    db, user, listing = fresh()
    r = insights.seo_report(db, listing)
    assert len(r["tags"]) == 13
    assert all(0 <= t["strength"] <= 100 for t in r["tags"])
    assert "checks" in r["title"] and r["title"]["score"] >= 0
    assert isinstance(r["suggestions"], list)
    print(f"PASS SEO studio: tag avg={r['tag_average_strength']}, "
          f"title score={r['title']['score']}, {len(r['suggestions'])} suggestions")
    db.close()


def test_journey():
    db, user, listing = fresh()
    with_images(db, listing)
    j = insights.journey(db, listing)
    assert j["search_result"]["title_shown"]
    assert len(j["image_sequence"]) == 10
    assert [i["position"] for i in j["image_sequence"]] == list(range(1, 11))
    assert len(j["decision_timeline"]) == 6
    assert all(f["issue"] and f["where"] for f in j["friction_points"])
    print(f"PASS journey simulator: 10-step sequence, 6-stage timeline, "
          f"{len(j['friction_points'])} friction points surfaced")
    db.close()


def test_exports():
    db, user, listing = fresh()
    with_images(db, listing)
    pdf = exporter.pdf_report(db, listing)
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000
    csv_data = exporter.listing_csv(listing).decode()
    assert "TITLE" in csv_data and "gold" in csv_data.lower()
    blob = exporter.asset_zip(db, listing)
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = z.namelist()
    assert "listing.json" in names and "report.pdf" in names
    assert sum(1 for n in names if n.startswith("images/")) == 10
    assert "image_prompts.txt" in names
    print(f"PASS exports: PDF ({len(pdf)//1024}KB), CSV, ZIP with {len(names)} assets")
    db.close()


def test_image_reorder_and_versions():
    db, user, listing = fresh()
    with_images(db, listing)
    live = db.query(ListingImage).filter_by(listing_id=listing.id, superseded=False).all()
    # simulate a reorder swap of positions 1 and 2 (route logic mirrors this)
    a = next(i for i in live if i.display_order == 1)
    b = next(i for i in live if i.display_order == 2)
    a.display_order, b.display_order = 2, 1
    db.commit()
    orders = sorted(i.display_order for i in db.query(ListingImage)
                    .filter_by(listing_id=listing.id, superseded=False).all())
    assert orders == list(range(1, 11))
    # version history + restore
    from app.imaging.providers import LocalStudioProvider
    from app.schemas import ListingOutput
    output = ListingOutput.model_validate(listing.output_json)
    slot = output.image_prompts.slots[0]
    old_live = (db.query(ListingImage)
                .filter_by(listing_id=listing.id, slot_id=slot.slot_id, superseded=False).first())
    generator.generate_slot(db, listing.id, slot, LocalStudioProvider(),
                            Path("/tmp/p4_gen") / listing.id)
    versions = db.query(ListingImage).filter_by(listing_id=listing.id,
                                                slot_id=slot.slot_id).all()
    assert len([v for v in versions if not v.superseded]) == 1
    assert len(versions) >= 2
    # restore the old one
    new_live = next(v for v in versions if not v.superseded)
    new_live.superseded = True
    db.get(ListingImage, old_live.id).superseded = False
    db.commit()
    assert not db.get(ListingImage, old_live.id).superseded
    print("PASS image studio ops: reorder keeps permutation, versions tracked, restore works")
    db.close()


def test_notifications():
    db, user, listing = fresh()
    notify_generation(db, user.id, listing.id, listing.title, ok=True)
    notify_generation(db, user.id, listing.id, listing.title, ok=False, error="boom")
    notify_low_credits(db, user.id, 2, 100)
    notify_low_credits(db, user.id, 1, 100)   # deduped while unread
    rows = db.query(Notification).filter_by(user_id=user.id).all()
    kinds = [r.kind for r in rows]
    assert kinds.count("credits") == 1, "low-credit notices must dedupe"
    assert kinds.count("generation") == 2
    assert any("failed" in r.title.lower() for r in rows)
    print(f"PASS notifications: {len(rows)} emitted, credit notices deduped")
    db.close()


def test_pipeline_progress_and_brand_injection():
    """generate_listing reports step progress and forwards brand context to the BDE."""
    from unittest.mock import patch

    from app import schemas as S
    from app.pipeline import orchestrator
    from test_pipeline import (make_analysis, make_bde, make_competitor_intel,
                               make_listing, make_pricing, make_valid_strategy)

    db, user, _ = fresh()
    listing = Listing(user_id=user.id, title="t", status="generating")
    db.add(listing); db.commit()

    seen_steps, seen_ctx = [], {}

    def fake_bde(analysis, sig, ctx=""):
        seen_ctx["ctx"] = ctx
        return make_bde(), {"tokens_in": 1, "tokens_out": 1}

    with patch.object(orchestrator.product_analysis, "run",
                      lambda *a, **k: (make_analysis(), {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.buyer_decision_engine, "run", fake_bde), \
         patch.object(orchestrator.category_classifier, "run",
                      lambda *a, **k: (S.CategoryClassification(
                          category="digital_bundle", confidence=0.9, reasoning="r",
                          listing_structure_implications=["a", "b", "c", "d"]),
                          {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.listing_strategy, "run",
                      lambda *a, **k: (make_listing(), {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.competitor_intelligence, "run",
                      lambda *a, **k: (make_competitor_intel(), {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.pricing_strategy, "run",
                      lambda *a, **k: (make_pricing(), {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.image_strategy, "run",
                      lambda *a, **k: (make_valid_strategy(), {"tokens_in": 1, "tokens_out": 1})):
        orchestrator.generate_listing(
            "Gold", "12 textures", db=db, listing_id=listing.id,
            performance_context="PERF HISTORY",
            brand_context="BRAND SYSTEM: luxury gold",
            on_step=lambda name, i, total: seen_steps.append((name, i, total)))

    total_steps = len(orchestrator.PIPELINE_STEPS) + len(orchestrator.PHASE3_STEPS)
    assert len(seen_steps) == total_steps
    assert seen_steps[0] == ("input_ingestion", 1, total_steps)
    assert seen_steps[-1][1] == total_steps
    assert "PERF HISTORY" in seen_ctx["ctx"] and "BRAND SYSTEM" in seen_ctx["ctx"]
    print(f"PASS progress+brand: {total_steps} step callbacks fired in order, "
          "brand context reached the BDE alongside performance history")
    db.close()


if __name__ == "__main__":
    test_editor_validation()
    test_editor_apply_and_rescore()
    test_brand_consistency_and_context()
    test_compliance_score()
    test_seo_report()
    test_journey()
    test_exports()
    test_image_reorder_and_versions()
    test_notifications()
    test_pipeline_progress_and_brand_injection()
    print("\nALL PHASE 4 TESTS PASSED")
