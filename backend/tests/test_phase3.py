"""
Phase 3 tests — imaging + publishing + analytics loop. No external keys needed:
images render via LocalStudioProvider (real pixels, really validated), Etsy
runs against a FakeTransport that mimics the v3 API.

Run: python tests/test_phase3.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import schemas as S
from app.database import (Base, EtsyConnection, ImageGenerationLog, Listing,
                          ListingImage, ListingMetric, PublishedListing, User,
                          SessionLocal, engine, init_db)
from app.imaging import generator
from app.imaging.generator import MANDATORY_SUFFIX, compile_generation_prompt
from app.etsy import optimizer
from app.etsy.client import EtsyClient
from app.etsy.publisher import build_payload, pre_publish_gate, publish_listing

from test_pipeline import (make_analysis, make_bde, make_listing,
                           make_valid_strategy)


def fresh_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    user = User(email="p3@test.com", password_hash="x")
    db.add(user)
    db.commit()
    return db, user


def make_output() -> S.ListingOutput:
    from app.pipeline import validator as v, scoring
    bde, listing, images = make_bde(), make_listing(), make_valid_strategy()
    ok, checks, _ = v.validate(images, bde)
    report = v.build_report(ok, checks, 1, [])
    scores = scoring.compute(bde, listing, images, report)
    classification = S.CategoryClassification(
        category="digital_product", confidence=0.95, reasoning="digital files",
        signals_considered=["lexical", "structural", "scenario"],
        listing_structure_implications=["a", "b", "c", "d"])
    from app.pipeline import output_formatter
    return output_formatter.run(make_analysis(), bde, classification, listing,
                                images, report, scores)


# ---------------------------------------------------------------------------

def test_prompt_compilation():
    strategy = make_valid_strategy()
    for slot in strategy.slots:
        prompt, style = compile_generation_prompt(slot)
        for req in ["LIGHTING:", "CAMERA:", "ENVIRONMENT:", "COMPOSITION:",
                    "PRODUCT FOCUS:", "REALISM:", "LENS DEFAULT:", MANDATORY_SUFFIX]:
            assert req in prompt, (slot.slot_id, req)
    print("PASS prompt compilation: all specs + mandatory suffix in all 7 prompts")


def test_generation_and_orchestration():
    db, user = fresh_db()
    listing = Listing(user_id=user.id, title="t", status="complete")
    db.add(listing); db.commit()
    strategy = make_valid_strategy()

    run = generator.generate_all(db, listing.id, strategy)
    assert len(run.images) == 7
    orders = sorted(g.display_order for g in run.images)
    assert orders == [1, 2, 3, 4, 5, 6, 7], orders
    assert run.sequence_report["valid"], run.sequence_report
    # position 1 must be the CTR hero
    pos1_slot = run.sequence_report["sequence"][0]["slot_id"]
    slot1 = next(s for s in strategy.slots if s.slot_id == pos1_slot)
    assert slot1.intent == S.ImageIntent.CTR
    # files really exist and are real images
    from PIL import Image
    for g in run.images:
        img = Image.open(g.image_url)
        assert img.size[0] >= 1000
        assert g.validation_score > 0
    # logs recorded every attempt
    logs = db.query(ImageGenerationLog).filter_by(listing_id=listing.id).all()
    assert len(logs) >= 7
    passed_final = db.query(ListingImage).filter_by(listing_id=listing.id, superseded=False).count()
    assert passed_final == 7
    print(f"PASS generation+orchestration: 7 real images, sequence valid, "
          f"{len(logs)} attempts logged, "
          f"regens={[g.regeneration_count for g in run.images]}")
    db.close()


def test_version_history_on_regenerate():
    db, user = fresh_db()
    listing = Listing(user_id=user.id, title="t", status="complete")
    db.add(listing); db.commit()
    strategy = make_valid_strategy()
    slot = strategy.slots[0]
    from app.imaging.providers import LocalStudioProvider
    out = Path("/tmp/lf_gen") / listing.id
    generator.generate_slot(db, listing.id, slot, LocalStudioProvider(), out)
    generator.generate_slot(db, listing.id, slot, LocalStudioProvider(), out)
    rows = db.query(ListingImage).filter_by(listing_id=listing.id, slot_id=slot.slot_id).all()
    live = [r for r in rows if not r.superseded]
    assert len(rows) >= 2 and len(live) == 1
    print("PASS version history: old versions superseded, one live per slot")
    db.close()


# ---------------------------------------------------------------------------
# Fake Etsy
# ---------------------------------------------------------------------------

class FakeTransport:
    def __init__(self):
        self.listings = {}
        self.images = {}
        self.next_id = 5000
        self.calls = []

    def request(self, method, url, *, headers=None, params=None, data=None,
                json=None, files=None):
        self.calls.append((method, url))
        if url.endswith("/public/oauth/token"):
            return {"access_token": "tok_new", "refresh_token": "ref_new", "expires_in": 3600}
        if url.endswith("/users/me"):
            return {"user_id": 77, "shop_id": 900}
        if method == "POST" and url.endswith("/listings"):
            lid = self.next_id; self.next_id += 1
            self.listings[str(lid)] = dict(data or {}, state="draft", views=0, num_favorers=0)
            self.images[str(lid)] = []
            return {"listing_id": lid, "url": f"https://etsy.test/listing/{lid}"}
        if "/images" in url and method == "POST":
            lid = url.split("/listings/")[1].split("/")[0]
            self.images[lid].append({"rank": (data or {}).get("rank"), "name": files["image"][0]})
            return {"listing_image_id": len(self.images[lid])}
        if method == "PATCH" and "/listings/" in url:
            lid = url.split("/listings/")[1].split("?")[0]
            self.listings[lid].update(data or {})
            return {"listing_id": lid}
        if method == "GET" and "/listings/active" in url:
            kw = (params or {}).get("keywords", "")
            return {"results": [
                {"title": f"{kw} premium seamless bundle mockup canva {i}",
                 "price": {"amount": 700 + i * 150, "divisor": 100},
                 "images": [{}] * 9} for i in range(6)]}
        if method == "GET" and "/listings/" in url:
            lid = url.split("/listings/")[1].split("?")[0]
            row = self.listings.get(lid, {})
            return {"listing_id": lid, "views": 320, "num_favorers": 24, **row}
        return {}


def _connected(db, user):
    conn = EtsyConnection(
        user_id=user.id, shop_id="900", shop_name="DigitalGlowPress",
        access_token="tok", refresh_token="ref",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(conn); db.commit()
    return conn


def test_publish_gate_blocks():
    output = make_output()
    gate = pre_publish_gate(output, images=[], taxonomy_id=2078)
    assert not gate.ok
    assert any("fewer than 7" in b for b in gate.blocks)
    gate2 = pre_publish_gate(output, images=[], taxonomy_id=None)
    assert any("taxonomy" in b for b in gate2.blocks)
    print("PASS publish gate blocks:", gate.blocks + gate2.blocks[-1:])


def test_full_publish_flow():
    db, user = fresh_db()
    output = make_output()
    listing = Listing(user_id=user.id, title="Gold Paper", status="complete",
                      input_price=8.99, category="digital_product",
                      output_json=output.model_dump(mode="json"))
    db.add(listing); db.commit()
    # generate real images first
    run = generator.generate_all(db, listing.id, output.image_prompts)
    conn = _connected(db, user)
    fake = FakeTransport()
    client = EtsyClient(api_key="key_test", transport=fake)

    record = publish_listing(db, listing, conn, price=8.99, activate=True, client=client)
    assert record.etsy_listing_id in fake.listings
    published = fake.listings[record.etsy_listing_id]
    assert published["state"] == "active"
    assert published["is_digital"] is True
    assert len(published["tags"]) == 13
    uploads = fake.images[record.etsy_listing_id]
    assert len(uploads) == 7
    assert [u["rank"] for u in uploads] == [1, 2, 3, 4, 5, 6, 7], "upload order must follow the psychological sequence"
    print("PASS full publish: draft→images(rank 1-7)→active, payload valid")
    db.close()


def test_payload_physical_vs_digital():
    output = make_output()
    p = build_payload(output, 8.99)
    assert p["type"] == "download" and p["is_digital"]
    output2 = make_output()
    output2.product_category = S.ProductCategory.physical_product
    p2 = build_payload(output2, 24.0, shipping_profile_id=123)
    assert p2["type"] == "physical" and p2["shipping_profile_id"] == 123
    assert "processing_min" in p2
    print("PASS payload: digital vs physical flags, shipping profile, processing time")


def test_analytics_loop():
    db, user = fresh_db()
    conn = _connected(db, user)
    listing = Listing(user_id=user.id, title="Gold Paper", status="complete",
                      output_json={"product_category": "digital_product"})
    db.add(listing); db.commit()
    pub = PublishedListing(listing_id=listing.id, user_id=user.id,
                           etsy_listing_id="5001", state="active",
                           payload_json={"title": "Gold Foil Digital Paper"})
    db.add(pub); db.commit()
    fake = FakeTransport()
    fake.listings["5001"] = {"state": "active"}
    n = optimizer.sync_metrics(db, conn, client=EtsyClient(api_key="k", transport=fake))
    assert n == 1
    m = db.query(ListingMetric).first()
    assert m.views == 320 and m.favorites == 24
    ctx = optimizer.performance_context(db, user.id)
    assert "SHOP PERFORMANCE HISTORY" in ctx and "favorite-rate" in ctx
    print("PASS analytics loop: metrics synced, performance context built:")
    print("   " + ctx.splitlines()[1])
    db.close()


def test_competitive_analysis():
    db, user = fresh_db()
    conn = _connected(db, user)
    output = make_output()
    listing = Listing(user_id=user.id, title="Gold Paper", status="complete",
                      input_price=29.99,  # deliberately >1.5x fake median
                      output_json=output.model_dump(mode="json"))
    db.add(listing); db.commit()
    fake = FakeTransport()
    result = optimizer.analyze(db, listing, conn,
                               client=EtsyClient(api_key="k", transport=fake),
                               use_llm=False)
    assert result["competitors_analyzed"] == 6
    areas = {r["area"] for r in result["optimization_recommendations"]}
    assert "pricing" in areas, areas
    assert "keyword_gaps" in areas or "image_gap" in areas, areas
    print("PASS competitive analysis:", areas)
    db.close()


def test_pipeline_phase3_steps_enforced():
    """Full orchestrator with db: all 11 steps must run and generated images
    must land in export_formats."""
    from app.pipeline import orchestrator
    db, user = fresh_db()
    listing = Listing(user_id=user.id, title="t", status="generating")
    db.add(listing); db.commit()
    analysis, bde, lst = make_analysis(), make_bde(), make_listing()

    with patch.object(orchestrator.product_analysis, "run",
                      lambda *a, **k: (analysis, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.buyer_decision_engine, "run",
                      lambda *a, **k: (bde, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.category_classifier, "run",
                      lambda *a, **k: (S.CategoryClassification(
                          category="digital_product", confidence=0.9, reasoning="r",
                          listing_structure_implications=["a", "b", "c", "d"]),
                          {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.listing_strategy, "run",
                      lambda *a, **k: (lst, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(orchestrator.image_strategy, "run",
                      lambda *a, **k: (make_valid_strategy(), {"tokens_in": 1, "tokens_out": 1})):
        result = orchestrator.generate_listing(
            "Gold Paper", "12 textures", db=db, listing_id=listing.id,
            performance_context="SHOP PERFORMANCE HISTORY: prior gold packs at 7% favorite rate")

    assert result.stage_log == list(orchestrator.PIPELINE_STEPS + orchestrator.PHASE3_STEPS)
    gen = result.output.export_formats["generated_images"]
    assert len(gen) == 7
    for g in gen:
        assert g["final_image_url"].endswith("/file")
        assert g["validation_score"] > 0
        assert MANDATORY_SUFFIX in g["generation_prompt"]
        assert g["style_profile"]
        assert isinstance(g["regeneration_count"], int)
    assert result.output.export_formats["image_sequence"]["valid"]
    print("PASS end-to-end 11-step pipeline: images generated inside the flow, "
          "all slot outputs carry url/prompt/style/score/regens")
    db.close()


if __name__ == "__main__":
    test_prompt_compilation()
    test_generation_and_orchestration()
    test_version_history_on_regenerate()
    test_publish_gate_blocks()
    test_full_publish_flow()
    test_payload_physical_vs_digital()
    test_analytics_loop()
    test_competitive_analysis()
    test_pipeline_phase3_steps_enforced()
    print("\nALL PHASE 3 TESTS PASSED")
