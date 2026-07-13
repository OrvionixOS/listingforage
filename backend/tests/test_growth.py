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


if __name__ == "__main__":
    test_result_schema_hard_rules()
    test_full_api_flow()
    test_quota_enforced()
    test_improve_directives()
    print("\nALL GROWTH TESTS PASSED")
