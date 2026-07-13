"""
Etsy Growth AI (ported etsy-elevate-ai app) — API + engine tests.

Full end-to-end through the HTTP layer with the model call mocked:
register → create product → generate → list/get listings → improve →
profile. Also validates the ListingResult schema hard rules (13 tags,
10-image sequence, title length).

Run: python tests/test_growth.py
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import elevate
from app.database import Base, engine, init_db
from app.main import app


def make_result(overall: int = 82, best_title: str = "Boho Wedding Invitation Template, Editable Canva Invite, Instant Download") -> dict:
    return {
        "productAnalysis": {
            "summary": "An editable boho wedding invitation template.",
            "idealBuyer": "Budget-savvy brides planning a boho wedding.",
            "buyingMotivation": "Wants designer-quality invites without designer prices.",
            "emotionalAppeal": "Feeling proud of beautiful, personal invitations.",
            "complexity": "Beginner-friendly",
            "useCases": ["weddings", "engagement parties"],
            "niches": ["boho weddings", "budget weddings"],
            "seasonalOpportunities": ["engagement season (Nov-Feb)"],
            "giftPotential": "Low — self-purchase product.",
            "premiumPositioning": "Position as a full suite, not a single card.",
        },
        "marketResearch": {
            "overview": "Crowded niche with weak personalization proof.",
            "competitorPatterns": ["Canva templates dominate", "Suites outsell singles"],
            "customerLanguage": ["easy to edit", "beautiful font"],
            "objections": ["Can I really edit this myself?"],
        },
        "marketGap": {
            "competitorsDoWell": ["Clean mockups"],
            "customersRespondTo": ["Video previews"],
            "competitorWeaknesses": ["No editing tutorial", "Vague license terms"],
            "differentiation": ["Step-by-step edit video", "Full matching suite"],
            "strongerOffer": "A complete suite with a guided editing experience.",
        },
        "beatBestSellers": {
            "positioning": "The stress-free boho suite.",
            "keywordStrategy": "Own long-tail boho + editable phrases.",
            "visualStrategy": "Show the editing experience, not just the design.",
            "valueProps": ["Full suite included", "Edit in 10 minutes"],
            "whyChooseThis": "It removes the editing fear competitors ignore.",
        },
        "brand": {
            "positioningStatement": "Effortless boho stationery for modern brides.",
            "idealCustomer": "DIY-confident brides aged 24-38.",
            "personality": ["warm", "organic", "unfussy"],
            "colors": [{"hex": "#C67B58", "name": "Terracotta"},
                       {"hex": "#EFE6DA", "name": "Sand"},
                       {"hex": "#7A8B6F", "name": "Sage"},
                       {"hex": "#3E3A36", "name": "Espresso"},
                       {"hex": "#D9C7B2", "name": "Linen"}],
            "typography": ["Serif display + humanist sans"],
            "collectionIdeas": ["Matching menu + program set"],
            "expansionIdeas": ["Bridal shower suite"],
            "consistencyGuidelines": ["Same palette across all mockups"],
        },
        "titles": {
            "best": best_title,
            "alternatives": ["Editable Boho Wedding Invite Template", "Boho Wedding Suite Canva Template"],
            "reasoning": "Front-loads the highest-volume keyword and states editability.",
        },
        "description": {
            "hook": "Your dream boho invites, ready tonight.",
            "problem": "Custom stationery is slow and expensive.",
            "transformation": "From engaged to invites-sent in one evening.",
            "included": ["5x7 invitation", "RSVP card", "Details card"],
            "features": ["Fully editable in free Canva", "Prints at home or any shop"],
            "fileDetails": "Canva template links + PDF guide.",
            "instructions": "Open the link, edit text, download, print.",
            "printing": "300 DPI, bleed included, prints anywhere.",
            "compatibility": "Works with free Canva. No fonts to install.",
            "faq": [{"q": "Can I change the colors?", "a": "Yes — every element is editable."}],
            "trust": "Instant delivery, lifetime access, quick support.",
            "cta": "Add to cart and send invites this week.",
            "fullText": "Your dream boho invites, ready tonight.\n\nWHAT'S INCLUDED...\n",
        },
        "tags": ["boho wedding invite", "editable invitation", "canva template",
                 "wedding suite", "instant download", "rustic wedding",
                 "invitation template", "diy wedding invite", "printable invite",
                 "terracotta wedding", "boho bridal", "wedding printable",
                 "rsvp card template"],
        "keywords": {
            "primary": ["boho wedding invitation template"],
            "secondary": ["editable wedding invite"],
            "longTail": ["boho wedding invitation template canva editable"],
        },
        "attributes": {
            "materials": ["digital file", "canva template"],
            "colors": ["terracotta", "sage"],
            "occasions": ["wedding"],
            "themes": ["boho"],
            "categories": ["Paper & Party Supplies"],
            "styles": ["bohemian"],
        },
        "pricing": {"recommended": 12.99, "min": 8.99, "max": 18.99,
                    "strategy": "Anchor against $200+ custom stationery."},
        "images": [{"n": i, "title": f"Image {i}", "purpose": "conversion",
                    "psychology": "trust", "layout": "grid",
                    "copyOverlay": "Editable in Canva", "designDirection": "warm light",
                    "mockup": "styled desk", "cta": "Edit yours today" if i == 10 else ""}
                   for i in range(1, 11)],
        "scores": {"seo": 84, "keywordOpportunity": 78, "competitiveAdvantage": 80,
                   "thumbnail": 75, "visualQuality": 77, "conversion": 83,
                   "brandAlignment": 81, "buyerConfidence": 79, "offerStrength": 85,
                   "overall": overall},
        "recommendations": ["Add a 15-second editing screen recording"],
    }


def fresh_client() -> tuple[TestClient, dict]:
    Base.metadata.drop_all(bind=engine)
    init_db()
    client = TestClient(app)
    r = client.post("/api/auth/register",
                    json={"email": "growth@test.com", "password": "testpass123"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return client, headers


def test_result_schema_hard_rules():
    ok = elevate.ListingResult.model_validate(make_result())
    assert len(ok.tags) == 13 and len(ok.images) == 10

    bad = make_result()
    bad["tags"] = bad["tags"][:12]
    try:
        elevate.ListingResult.model_validate(bad)
        raise AssertionError("12 tags must be rejected")
    except Exception:
        pass

    bad = make_result()
    bad["tags"][0] = "this tag is way over twenty characters"
    try:
        elevate.ListingResult.model_validate(bad)
        raise AssertionError("oversized tag must be rejected")
    except Exception:
        pass

    bad = make_result()
    bad["images"][3]["n"] = 3  # duplicate position
    try:
        elevate.ListingResult.model_validate(bad)
        raise AssertionError("broken 1-10 image sequence must be rejected")
    except Exception:
        pass
    print("PASS ListingResult hard rules: 13 tags, tag length, 10-image sequence")


def test_full_api_flow():
    client, headers = fresh_client()
    result = elevate.ListingResult.model_validate(make_result())

    with patch.object(elevate, "generate",
                      lambda product, competitors="", keywords="": (result, {"tokens_in": 5, "tokens_out": 5})):
        p = client.post("/api/growth/products", headers=headers,
                        json={"name": "Boho Wedding Invitation Template",
                              "category": "Invitation", "style": "Boho",
                              "target_audience": "Brides", "notes": "Canva, 3 cards"})
        assert p.status_code == 200, p.text
        product_id = p.json()["id"]

        g = client.post("/api/growth/generate", headers=headers,
                        json={"product_id": product_id, "competitors": "", "keywords": ""})
        assert g.status_code == 200, g.text
        listing_id = g.json()["listing_id"]
        assert g.json()["result"]["scores"]["overall"] == 82

    ls = client.get("/api/growth/listings", headers=headers).json()
    assert len(ls) == 1 and ls[0]["score"] == 82
    assert ls[0]["products"]["name"] == "Boho Wedding Invitation Template"

    one = client.get(f"/api/growth/listings/{listing_id}", headers=headers).json()
    assert one["result"]["titles"]["best"].startswith("Boho Wedding")
    assert len(one["result"]["images"]) == 10

    improved = elevate.ListingResult.model_validate(
        make_result(overall=91, best_title="Premium Boho Wedding Invitation Suite, Editable Canva Template"))
    with patch.object(elevate, "improve",
                      lambda product, cur, action, instruction="": (improved, {"tokens_in": 5, "tokens_out": 5})):
        im = client.post(f"/api/growth/listings/{listing_id}/improve", headers=headers,
                         json={"action": "premium"})
        assert im.status_code == 200, im.text
    one2 = client.get(f"/api/growth/listings/{listing_id}", headers=headers).json()
    assert one2["score"] == 91 and one2["title"].startswith("Premium Boho")

    prof = client.patch("/api/growth/profile", headers=headers,
                        json={"display_name": "Fay", "brand_name": "Sand & Sage Studio"})
    assert prof.json()["brand_name"] == "Sand & Sage Studio"
    assert client.get("/api/growth/profile", headers=headers).json()["display_name"] == "Fay"

    d = client.delete(f"/api/growth/listings/{listing_id}", headers=headers)
    assert d.json()["ok"]
    assert client.get("/api/growth/listings", headers=headers).json() == []
    print("PASS full API flow: register → product → generate → listings → improve → profile → delete")


def test_quota_enforced():
    client, headers = fresh_client()
    result = elevate.ListingResult.model_validate(make_result())
    p = client.post("/api/growth/products", headers=headers, json={"name": "Pack"})
    pid = p.json()["id"]
    with patch.object(elevate, "generate",
                      lambda *a, **k: (result, {"tokens_in": 1, "tokens_out": 1})):
        for _ in range(3):  # free tier: 3/month
            assert client.post("/api/growth/generate", headers=headers,
                               json={"product_id": pid}).status_code == 200
        over = client.post("/api/growth/generate", headers=headers, json={"product_id": pid})
    assert over.status_code == 402, over.text
    print("PASS quota: free tier capped at 3 generations, 4th returns 402")


def test_improve_directives():
    """Every UI improve action maps to a real directive; audience appends instruction."""
    for key in ("regenerate", "seo", "conversion", "premium", "trendy", "gift", "audience", "compete"):
        assert key in elevate.IMPROVE_ACTIONS, key

    seen = {}

    def fake_call(system, content, schema, **kw):
        seen["content"] = content
        return elevate.ListingResult.model_validate(make_result()), {"tokens_in": 1, "tokens_out": 1}

    from types import SimpleNamespace
    product = SimpleNamespace(name="Pack", category=None, style=None,
                              target_audience=None, notes=None, files=[])
    with patch.object(elevate, "structured_call", fake_call):
        elevate.improve(product, make_result(), "audience", "target wedding planners")
    assert "Reposition for a different, higher-value target audience" in seen["content"]
    assert "target wedding planners" in seen["content"]
    with patch.object(elevate, "structured_call", fake_call):
        elevate.improve(product, make_result(), "not-a-real-action")
    assert "Maximize conversion" in seen["content"], "unknown action falls back to conversion"
    print("PASS improve directives: all 8 actions present, audience instruction forwarded, safe fallback")


def make_identification() -> dict:
    return {
        "product_type": "luxury metallic digital paper / seamless texture pack",
        "positioning": "These have a premium, interior-design feel rather than a scrapbook "
                       "aesthetic. Position them as luxury digital papers, seamless backgrounds "
                       "and texture overlays — that attracts higher-value buyers.",
        "suggested_name": "Luxury Metallic Digital Paper Bundle",
        "category": "Graphics & Digital Assets / Textures",
        "style": "Luxury",
        "target_buyers": ["graphic designers", "branding agencies", "invitation designers"],
        "seo_title": "Luxury Metallic Digital Paper Bundle, Gold Silver Copper Rose Gold "
                     "Textures, Seamless Backgrounds, Commercial Use",
        "tags": ["gold texture", "silver texture", "metallic paper", "luxury background",
                 "rose gold texture", "copper background", "foil digital paper",
                 "wedding background", "branding texture", "elegant paper",
                 "premium paper", "luxury scrapbook", "seamless texture"],
        "collection_ideas": ["Luxe Surfaces Vol. 1 — Sculpted Plaster",
                             "Luxe Surfaces Vol. 2 — Metallic Weaves",
                             "Luxe Surfaces Vol. 3 — Concrete Minimalism",
                             "Luxe Surfaces Vol. 4 — Liquid Chrome"],
        "shop_branding_note": "'Luxe Surfaces' feels cohesive, premium and collectible — the "
                              "shop reads as a curated design resource.",
        "observed_details": "5 seamless metallic textures: gold foil, brushed silver, copper, "
                            "rose gold, chrome. High-res, no text overlays.",
    }


def _tiny_png() -> bytes:
    from io import BytesIO

    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (64, 64), (200, 160, 90)).save(buf, "PNG")
    return buf.getvalue()


def test_identification_schema():
    ok = elevate.ProductIdentification.model_validate(make_identification())
    assert len(ok.tags) == 13
    bad = make_identification()
    bad["tags"][0] = "way too long for an etsy tag field"
    try:
        elevate.ProductIdentification.model_validate(bad)
        raise AssertionError("oversized tag must be rejected")
    except Exception:
        pass
    print("PASS identification schema: 13 tags enforced, tag length enforced")


def test_upload_identify_and_grounded_generation():
    """Upload real images → identify (vision mocked) → product carries the
    files → generate() attaches them as image blocks for grounding."""
    client, headers = fresh_client()

    ids = []
    for i in range(2):
        r = client.post("/api/growth/uploads", headers=headers,
                        files={"file": (f"tex{i}.png", _tiny_png(), "image/png")})
        assert r.status_code == 200, r.text
        ids.append(r.json()["upload_id"])

    ident = elevate.ProductIdentification.model_validate(make_identification())
    seen_paths = {}

    def fake_identify(paths):
        seen_paths["paths"] = paths
        return ident, {"tokens_in": 1, "tokens_out": 1}

    with patch.object(elevate, "identify_product", fake_identify):
        r = client.post("/api/growth/identify", headers=headers, json={"upload_ids": ids})
    assert r.status_code == 200, r.text
    assert r.json()["seo_title"].startswith("Luxury Metallic")
    assert len(r.json()["tags"]) == 13
    assert len(seen_paths["paths"]) == 2 and all(Path(p).exists() for p in seen_paths["paths"])

    # unknown upload ids are rejected
    bad = client.post("/api/growth/identify", headers=headers, json={"upload_ids": ["nope"]})
    assert bad.status_code == 400

    # product created with upload_ids carries the file paths
    p = client.post("/api/growth/products", headers=headers,
                    json={"name": ident.suggested_name, "category": ident.category,
                          "style": ident.style, "upload_ids": ids})
    assert len(p.json()["files"]) == 2

    # generate() must attach the images as vision blocks
    captured = {}

    def fake_call(system, content, schema, **kw):
        captured["content"] = content
        return elevate.ListingResult.model_validate(make_result()), {"tokens_in": 1, "tokens_out": 1}

    with patch.object(elevate, "structured_call", fake_call):
        g = client.post("/api/growth/generate", headers=headers,
                        json={"product_id": p.json()["id"]})
    assert g.status_code == 200, g.text
    content = captured["content"]
    assert isinstance(content, list), "image-grounded generation must send content blocks"
    image_blocks = [b for b in content if b.get("type") == "image"]
    assert len(image_blocks) == 2
    text_block = next(b for b in content if b.get("type") == "text")
    assert "The attached images and files ARE the product" in text_block["text"]
    print("PASS upload→identify→grounded generation: files stored, vision paths real, "
          "generation received 2 image blocks")


def test_minimal_intake_asset_analysis_and_autoname():
    """The no-questions flow: no product name, a ZIP product file, brand style.
    The ZIP is inventoried into the prompt, brand fields reach the brief, and
    the product is auto-named from the generated title."""
    import io
    import zipfile as zf

    client, headers = fresh_client()

    # image (required) + zip product file (optional, kind=asset)
    img = client.post("/api/growth/uploads", headers=headers,
                      files={"file": ("cover.png", _tiny_png(), "image/png")})
    zbuf = io.BytesIO()
    with zf.ZipFile(zbuf, "w") as z:
        for i in range(4):
            z.writestr(f"papers/texture_{i}.png", b"fake")
        z.writestr("README.pdf", b"fake")
    asset = client.post("/api/growth/uploads?kind=asset", headers=headers,
                        files={"file": ("gold-pack.zip", zbuf.getvalue(), "application/zip")})
    assert asset.status_code == 200, asset.text

    # a zip must be rejected on the default image-only kind
    zbuf.seek(0)
    rejected = client.post("/api/growth/uploads", headers=headers,
                           files={"file": ("x.zip", zbuf.getvalue(), "application/zip")})
    assert rejected.status_code == 400

    p = client.post("/api/growth/products", headers=headers,
                    json={"category": "Graphics & Digital Assets / Textures",
                          "style": "Luxury", "brand_name": "Luxe Surfaces",
                          "color_preferences": "gold, ivory",
                          "file_link": "https://www.canva.com/design/abc",
                          "upload_ids": [img.json()["upload_id"]],
                          "asset_upload_ids": [asset.json()["upload_id"]]})
    assert p.status_code == 200, p.text
    assert p.json()["name"] == "Untitled product"
    kinds = sorted(f["kind"] for f in p.json()["files"])
    assert kinds == ["asset", "image"]

    captured = {}

    def fake_call(system, content, schema, **kw):
        captured["content"] = content
        return elevate.ListingResult.model_validate(make_result()), {"tokens_in": 1, "tokens_out": 1}

    with patch.object(elevate, "structured_call", fake_call):
        g = client.post("/api/growth/generate", headers=headers,
                        json={"product_id": p.json()["id"]})
    assert g.status_code == 200, g.text

    content = captured["content"]
    assert isinstance(content, list)
    text = next(b for b in content if b.get("type") == "text")["text"]
    assert "PRODUCT FILE CONTENTS" in text and "ZIP containing 5 files" in text
    assert "4x .png" in text and "BRAND NAME: Luxe Surfaces" in text
    assert "gold, ivory" in text and "canva.com" in text
    assert "infer the best product name" in text

    # product auto-named from the generated best title
    products = client.get("/api/growth/products", headers=headers).json()
    assert products[0]["name"].startswith("Boho Wedding Invitation Template")
    print("PASS minimal intake: zip inventoried into prompt, brand fields briefed, "
          "zip rejected as image, product auto-named from result")


def test_real_identify_builds_blocks(tmp_path=None):
    """identify_product itself: reads real pixels into base64 blocks, rejects empty."""
    import tempfile
    d = Path(tempfile.mkdtemp())
    img = d / "a.png"
    img.write_bytes(_tiny_png())

    captured = {}

    def fake_call(system, content, schema, **kw):
        captured["system"] = system
        captured["content"] = content
        return elevate.ProductIdentification.model_validate(make_identification()), {"tokens_in": 1, "tokens_out": 1}

    with patch.object(elevate, "structured_call", fake_call):
        result, _ = elevate.identify_product([str(img)])
    assert result.category == "Graphics & Digital Assets / Textures"
    blocks = [b for b in captured["content"] if b.get("type") == "image"]
    assert len(blocks) == 1 and blocks[0]["source"]["media_type"] == "image/jpeg", \
        "images are downscaled and re-encoded as JPEG for the vision call"
    assert "product identification engine" in captured["system"]

    try:
        elevate.identify_product([str(d / "missing.png")])
        raise AssertionError("no readable images must raise")
    except ValueError:
        pass
    print("PASS identify_product: real pixels become vision blocks, empty input rejected")


# ------------------------------------------------------------------------------
# Growth Lab
# ------------------------------------------------------------------------------

def make_thumb_sim() -> dict:
    return {
        "variations": [
            {"n": i, "concept": f"Concept {i}", "textPlacement": "bottom band",
             "productSize": "fills 80% of frame", "colorContrast": "warm on dark",
             "visualHierarchy": "product → badge → text",
             "predictedCtr": 60 + i * 4, "reasoning": "strong at 180px"}
            for i in range(1, 6)
        ],
        "winner": 5, "winnerRationale": "Highest contrast and clearest hierarchy.",
        "competitorComparison": "Competitors use flat beige mockups; this pops in the grid.",
    }


def make_upgrade_plan() -> dict:
    return {
        "currentOffer": "50 printable affirmation cards.",
        "upgrades": [
            {"addition": "Matching phone wallpapers", "whyItWorks": "Daily visibility",
             "effort": "low", "valueImpact": "Feels like a lifestyle system"},
            {"addition": "Journal prompts", "whyItWorks": "Deepens use", "effort": "low",
             "valueImpact": "Adds a second use case"},
            {"addition": "Printable altar cards", "whyItWorks": "Niche ritual value",
             "effort": "medium", "valueImpact": "Premium feel"},
            {"addition": "Canva editable version", "whyItWorks": "Personalization",
             "effort": "medium", "valueImpact": "Justifies premium price"},
        ],
        "upgradedOffer": "The complete affirmation ritual kit.",
        "priceFrom": 5.0, "priceTo": 15.0,
        "pricingRationale": "Bundle perception triples perceived value.",
    }


def make_expansion_plan() -> dict:
    return {
        "collectionName": "Lunar Ritual Collection",
        "ideas": [{"name": f"Product {i}", "subcategory": "Wellness & Spirituality / Manifestation journals",
                   "whyItSells": "Same buyer, same aesthetic", "priceRange": "$6-$12"}
                  for i in range(1, 13)],
        "launchOrder": ["Astrology journal first — highest search volume",
                        "Lunar planner second", "Zodiac stickers third"],
        "crossSellStrategy": "Every listing links the collection; bundle discount on 3+.",
    }


def make_teardown() -> dict:
    return {
        "competitor": {
            "title": "100 Page Digital Planner", "price": 9.99,
            "tags": ["digital planner", "goodnotes planner"], "imageCount": 7,
            "reviewSignals": ["praise: easy to use", "complaint: no editing tutorial"],
            "strengths": ["Clean covers", "Strong review count"],
            "weaknesses": ["No video tutorial", "Only 100 pages, no extras"],
        },
        "gaps": ["No editable Canva version", "No stickers included", "Weak lifestyle imagery"],
        "positioningPlan": "Position as the complete planning system, not just a planner.",
        "upgradedOffer": "150-page planner + stickers + trackers + editable Canva version.",
        "data_source": "model_knowledge",
    }


def test_growth_lab_tools_persist():
    """Thumbnails/upgrades/expansion run per-listing and persist into result_json."""
    client, headers = fresh_client()
    result = elevate.ListingResult.model_validate(make_result())
    p = client.post("/api/growth/products", headers=headers, json={"name": "Cards"})
    with patch.object(elevate, "generate", lambda *a, **k: (result, {"tokens_in": 1, "tokens_out": 1})):
        g = client.post("/api/growth/generate", headers=headers,
                        json={"product_id": p.json()["id"]})
    lid = g.json()["listing_id"]

    sim = elevate.ThumbnailSimulation.model_validate(make_thumb_sim())
    up = elevate.UpgradePlan.model_validate(make_upgrade_plan())
    ex = elevate.ExpansionPlan.model_validate(make_expansion_plan())
    with patch.object(elevate, "thumbnail_simulation", lambda *a, **k: (sim, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(elevate, "upgrade_plan", lambda *a, **k: (up, {"tokens_in": 1, "tokens_out": 1})), \
         patch.object(elevate, "expansion_plan", lambda *a, **k: (ex, {"tokens_in": 1, "tokens_out": 1})):
        t = client.post(f"/api/growth/listings/{lid}/thumbnails", headers=headers)
        u = client.post(f"/api/growth/listings/{lid}/upgrades", headers=headers)
        e = client.post(f"/api/growth/listings/{lid}/expansion", headers=headers)
    assert t.json()["winner"] == 5
    assert u.json()["priceTo"] == 15.0
    assert len(e.json()["ideas"]) == 12

    # persisted alongside the ListingResult and returned on later reads
    got = client.get(f"/api/growth/listings/{lid}", headers=headers).json()["result"]
    assert got["thumbnailSimulation"]["winner"] == 5
    assert got["upgradePlan"]["upgradedOffer"].startswith("The complete")
    assert got["expansionPlan"]["collectionName"] == "Lunar Ritual Collection"
    assert got["titles"]["best"], "original ListingResult must survive the merge"
    print("PASS Growth Lab persistence: thumbnails/upgrades/expansion stored with the listing")


def test_beat_competitor_flow():
    """URL parse → live facts (faked transport) → teardown + rebuilt listing,
    provenance engine-enforced."""
    assert elevate._parse_etsy_listing_id("https://www.etsy.com/listing/123456789/foo-bar") == "123456789"
    assert elevate._parse_etsy_listing_id("https://www.etsy.com/uk/listing/42/x?ref=1") == "42"
    assert elevate._parse_etsy_listing_id("https://example.com/nope") is None

    client, headers = fresh_client()
    p = client.post("/api/growth/products", headers=headers, json={"name": "My Planner"})

    teardown = elevate.CompetitorTeardown.model_validate(make_teardown())
    rebuilt = elevate.ListingResult.model_validate(
        make_result(overall=93, best_title="Complete 150 Page Digital Planner System, Stickers + Trackers + Canva"))

    def fake_beat(product, url):
        assert "etsy.com/listing/555" in url
        td = teardown.model_copy(deep=True)
        td.data_source = "live_etsy_data"
        return td, rebuilt, {"tokens_in": 2, "tokens_out": 2}

    with patch.object(elevate, "beat_competitor", fake_beat):
        r = client.post("/api/growth/beat-competitor", headers=headers,
                        json={"product_id": p.json()["id"],
                              "competitor_url": "https://www.etsy.com/listing/555/planner"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["teardown"]["data_source"] == "live_etsy_data"
    assert body["teardown"]["competitor_url"].endswith("/555/planner")

    got = client.get(f"/api/growth/listings/{body['listing_id']}", headers=headers).json()
    assert got["score"] == 93
    assert got["result"]["competitorTeardown"]["competitor"]["title"] == "100 Page Digital Planner"
    print("PASS beat-competitor: URL parsing, new listing created with teardown attached")


def test_fetch_competitor_facts_live_and_fallback():
    """Live competitor fetch through a fake Etsy transport + honest fallbacks."""

    class FakeT:
        def request(self, method, url, **kw):
            if url.endswith("/reviews"):
                return {"results": [{"rating": 4, "review": "Love it but no tutorial included."}]}
            return {"title": "Boho Planner", "description": "A planner.",
                    "price": {"amount": 999, "divisor": 100},
                    "tags": ["planner"], "num_favorers": 200, "views": 5000,
                    "images": [{}] * 8}

    with patch("app.etsy.client.EtsyClient.__init__",
               lambda self, api_key=None, transport=None: (
                   setattr(self, "api_key", "k") or setattr(self, "transport", FakeT()) or
                   setattr(self, "redirect_uri", "x"))):
        facts, source = elevate.fetch_competitor_facts("https://www.etsy.com/listing/777/x")
    assert source == "live_etsy_data"
    assert "Boho Planner" in facts and "$9.99" in facts and "no tutorial" in facts
    assert "IMAGE COUNT: 8" in facts

    facts2, source2 = elevate.fetch_competitor_facts("https://not-etsy.com/x")
    assert source2 == "model_knowledge" and "could not parse" in facts2
    print("PASS competitor facts: live fetch measured, non-Etsy URL degrades honestly")


def test_startup_migration_adds_missing_columns():
    """Reproduces the production failure: a products table created BEFORE
    brand_name/color_preferences/file_link existed (persistent SQLite disk on
    Render) must be auto-migrated at startup instead of crashing queries."""
    from sqlalchemy import inspect, text

    from app.database import Base, Product, SessionLocal, engine, init_db

    Base.metadata.drop_all(bind=engine)
    # old-schema products table, as an earlier deploy created it
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE products (
                id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL, category VARCHAR, style VARCHAR,
                target_audience TEXT, notes TEXT, files JSON,
                thumbnail_url VARCHAR, created_at DATETIME)"""))
        conn.execute(text(
            "INSERT INTO products (id, user_id, name) VALUES ('p1', 'u1', 'Old Product')"))

    init_db()  # must add the new columns without touching existing data

    cols = {c["name"] for c in inspect(engine).get_columns("products")}
    for needed in ("brand_name", "color_preferences", "file_link"):
        assert needed in cols, f"startup migration must add {needed}"

    db = SessionLocal()
    row = db.query(Product).filter(Product.user_id == "u1").first()  # the query that crashed
    assert row is not None and row.name == "Old Product" and row.brand_name is None
    db.close()
    print("PASS startup migration: old-schema table gains new columns, data intact, query works")


def test_listing_package():
    client, headers = fresh_client()
    result = elevate.ListingResult.model_validate(make_result())
    p = client.post("/api/growth/products", headers=headers,
                    json={"name": "Pack", "category": "Paper & Party Supplies / Invitations"})
    with patch.object(elevate, "generate", lambda *a, **k: (result, {"tokens_in": 1, "tokens_out": 1})):
        g = client.post("/api/growth/generate", headers=headers,
                        json={"product_id": p.json()["id"]})
    r = client.get(f"/api/growth/listings/{g.json()['listing_id']}/package", headers=headers)
    pkg = r.json()["package"]
    for section in ["ETSY LISTING PACKAGE", "TITLE", "DESCRIPTION", "13 TAGS",
                    "CATEGORY", "PRICING", "CUSTOMER AVATAR", "PRODUCT POSITIONING",
                    "FILE DELIVERY INSTRUCTIONS", "10 LISTING IMAGES"]:
        assert section in pkg, section
    assert "Paper & Party Supplies / Invitations" in pkg
    assert "boho wedding invite" in pkg  # tags made it in
    assert pkg.count("Psychology:") == 10
    print("PASS one-click package: all 9 sections present, 10 image briefs included")


if __name__ == "__main__":
    test_result_schema_hard_rules()
    test_full_api_flow()
    test_quota_enforced()
    test_improve_directives()
    test_identification_schema()
    test_upload_identify_and_grounded_generation()
    test_minimal_intake_asset_analysis_and_autoname()
    test_real_identify_builds_blocks()
    test_growth_lab_tools_persist()
    test_beat_competitor_flow()
    test_fetch_competitor_facts_live_and_fallback()
    test_startup_migration_adds_missing_columns()
    test_listing_package()
    print("\nALL GROWTH TESTS PASSED")
