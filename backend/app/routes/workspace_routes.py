"""Workspace routes: dashboard overview, notifications, brand studio, bulk ops."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..billing import check_quota
from ..brandctx import brand_context
from ..database import (BrandProfile, Listing, ListingMetric, Notification,
                        PublishedListing, SessionLocal, User, get_db)
from ..schemas import GenerateRequest

log = logging.getLogger("listingforge.workspace")
router = APIRouter(prefix="/api/workspace", tags=["workspace"])


# ---------------------------------------------------------------------------
# Dashboard overview
# ---------------------------------------------------------------------------

@router.get("/overview")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listings = (db.query(Listing).filter(Listing.user_id == user.id)
                .order_by(Listing.updated_at.desc()).limit(200).all())
    published = db.query(PublishedListing).filter(PublishedListing.user_id == user.id).all()
    pub_ids = {p.id for p in published}
    latest_metrics = {}
    if pub_ids:
        for m in (db.query(ListingMetric)
                  .filter(ListingMetric.published_listing_id.in_(pub_ids))
                  .order_by(ListingMetric.captured_at.desc()).all()):
            latest_metrics.setdefault(m.published_listing_id, m)
    views = sum(m.views for m in latest_metrics.values())
    favs = sum(m.favorites for m in latest_metrics.values())
    _, quota = check_quota(db, user)
    unread = (db.query(Notification)
              .filter(Notification.user_id == user.id, Notification.read.is_(False)).count())

    # AI recommendations: cheap deterministic nudges from current state
    recs = []
    drafts = [l for l in listings if l.status == "complete"
              and l.id not in {p.listing_id for p in published}]
    if drafts:
        recs.append({"title": f"{len(drafts)} finished listing(s) not yet on Etsy",
                     "action": "Open the Publish tab and push them live.",
                     "link": drafts[0].id})
    failed = [l for l in listings if l.status == "failed"]
    if failed:
        recs.append({"title": f"{len(failed)} generation(s) failed",
                     "action": "Open the listing to see the error and retry.",
                     "link": failed[0].id})
    low_scores = []
    for l in listings[:20]:
        try:
            cs = (l.output_json or {}).get("conversion_scores", {})
            conv = cs.get("conversion_score", {}).get("score")
            if conv is not None and conv < 60:
                low_scores.append((l, conv))
        except Exception:
            pass
    if low_scores:
        l, conv = low_scores[0]
        recs.append({"title": f"“{l.title[:40]}” scores {conv}/100 on conversion",
                     "action": "Use the Editor's AI assist on title and trust blocks.",
                     "link": l.id})
    if quota["limit"] and quota["remaining"] <= max(1, quota["limit"] // 10):
        recs.append({"title": f"Only {quota['remaining']} generations left this cycle",
                     "action": "Upgrade in Plan & usage to keep shipping.", "link": None})

    profile = db.query(BrandProfile).filter(BrandProfile.user_id == user.id).first()
    return {
        "counts": {
            "total": len(listings),
            "generating": sum(1 for l in listings if l.status == "generating"),
            "drafts": len(drafts),
            "published": len(published),
            "failed": len(failed),
        },
        "performance": {"published": len(published), "views": views, "favorites": favs,
                        "favorite_rate": round(favs / views, 4) if views else None},
        "recent": [{"id": l.id, "title": l.title, "status": l.status,
                    "category": l.category,
                    "progress": l.progress_json,
                    "updated_at": l.updated_at.isoformat()} for l in listings[:8]],
        "recommendations": recs[:5],
        "quota": quota,
        "plan": user.plan,
        "unread_notifications": unread,
        "brand_configured": bool(profile and (profile.voice or profile.messaging_pillars)),
    }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Notification).filter(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc()).limit(50).all())
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
             "link": n.link, "read": n.read, "created_at": n.created_at.isoformat()}
            for n in rows]


@router.post("/notifications/read")
def mark_read(body: dict, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    ids = body.get("ids")
    if ids:
        q = q.filter(Notification.id.in_(ids))
    q.update({"read": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Brand Studio
# ---------------------------------------------------------------------------

@router.get("/brand")
def get_brand(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(BrandProfile).filter(BrandProfile.user_id == user.id).first()
    if p is None:
        return {"configured": False, "brand_name": "", "voice": "",
                "photography_style": "", "packaging_guidelines": "",
                "messaging_pillars": [], "palette": "", "apply_to_generations": True}
    return {"configured": True, "brand_name": p.brand_name, "voice": p.voice,
            "photography_style": p.photography_style,
            "packaging_guidelines": p.packaging_guidelines,
            "messaging_pillars": p.messaging_pillars or [],
            "palette": p.palette, "apply_to_generations": p.apply_to_generations}


@router.put("/brand")
def put_brand(body: dict, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    p = db.query(BrandProfile).filter(BrandProfile.user_id == user.id).first()
    if p is None:
        p = BrandProfile(user_id=user.id)
        db.add(p)
    for f in ("brand_name", "voice", "photography_style",
              "packaging_guidelines", "palette"):
        if f in body:
            setattr(p, f, str(body[f])[:2000])
    if "messaging_pillars" in body:
        pillars = body["messaging_pillars"]
        if not isinstance(pillars, list) or len(pillars) > 12:
            raise HTTPException(400, "messaging_pillars must be a list of up to 12 items.")
        p.messaging_pillars = [str(x)[:120] for x in pillars]
    if "apply_to_generations" in body:
        p.apply_to_generations = bool(body["apply_to_generations"])
    db.commit()
    return {"ok": True, "context_preview": brand_context(db, user.id)}


# ---------------------------------------------------------------------------
# Bulk generation
# ---------------------------------------------------------------------------

@router.post("/bulk/generate")
def bulk_generate(body: dict, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    items = body.get("items", [])
    if not isinstance(items, list) or not (1 <= len(items) <= 25):
        raise HTTPException(400, "Provide 1-25 items.")
    for i, item in enumerate(items):
        if not str(item.get("title", "")).strip() or not str(item.get("description", "")).strip():
            raise HTTPException(400, f"Item {i + 1}: title and description are required.")
    ok, quota = check_quota(db, user)
    if not ok or (quota["limit"] and quota["remaining"] < len(items)):
        raise HTTPException(402, f"Batch needs {len(items)} generations; "
                                 f"{quota.get('remaining', 0)} remaining this cycle.")
    import uuid
    batch_id = uuid.uuid4().hex[:12]
    ids = []
    for item in items:
        listing = Listing(user_id=user.id, title=str(item["title"])[:200],
                          input_description=str(item.get("description", "")),
                          input_price=item.get("price"),
                          input_notes=item.get("notes"),
                          status="queued", batch_id=batch_id)
        db.add(listing)
        db.commit()
        ids.append(listing.id)
    from ..jobs import enqueue
    for listing_id, item in zip(ids, items):
        req = GenerateRequest(title=item["title"],
                              description=item.get("description", ""),
                              price=item.get("price"), notes=item.get("notes"),
                              image_ids=[])
        enqueue(db, user.id, "generate_listing",
                {"listing_id": listing_id, "req": req.model_dump(mode="json"),
                 "image_paths": [], "batch_id": batch_id})
    return {"batch_id": batch_id, "listing_ids": ids, "queued": len(ids)}


@router.get("/bulk/{batch_id}")
def bulk_status(batch_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    rows = (db.query(Listing)
            .filter(Listing.batch_id == batch_id, Listing.user_id == user.id).all())
    if not rows:
        raise HTTPException(404, "Unknown batch.")
    return {"batch_id": batch_id,
            "items": [{"id": l.id, "title": l.title, "status": l.status,
                       "progress": l.progress_json, "error": l.error} for l in rows],
            "done": all(l.status in ("complete", "failed") for l in rows)}
