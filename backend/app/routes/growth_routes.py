"""
Etsy Growth AI API — products, listing generation/improvement, profile.

These endpoints power the ported etsy-elevate-ai frontend one-to-one:
  POST /api/growth/products                     create a product
  GET  /api/growth/products                     list products
  POST /api/growth/generate                     product -> full ListingResult
  GET  /api/growth/listings                     list listings (with product name)
  GET  /api/growth/listings/{id}                one listing
  POST /api/growth/listings/{id}/improve        improve with an action directive
  DELETE /api/growth/listings/{id}
  GET  /api/growth/profile / PATCH              display + brand name

Generation is synchronous (the UI shows an animated step list while the
request runs), exactly like the original app.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import elevate
from ..auth import get_current_user
from ..billing import check_quota, record_usage
from ..database import GrowthListing, Product, Profile, User, get_db

router = APIRouter(prefix="/api/growth", tags=["growth"])


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    category: str | None = None
    style: str | None = None
    target_audience: str | None = None
    notes: str | None = None


class GenerateBody(BaseModel):
    product_id: str
    competitors: str = ""
    keywords: str = ""


class ImproveBody(BaseModel):
    action: str
    instruction: str = ""


class ProfileBody(BaseModel):
    display_name: str | None = None
    brand_name: str | None = None


def _product_dict(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "category": p.category, "style": p.style,
            "target_audience": p.target_audience, "notes": p.notes,
            "files": p.files or [], "thumbnail_url": p.thumbnail_url,
            "created_at": p.created_at.isoformat() if p.created_at else None}


def _listing_dict(l: GrowthListing, product: Product | None, with_result: bool = True) -> dict:
    d = {"id": l.id, "product_id": l.product_id, "title": l.title,
         "status": l.status, "score": l.score, "saved": l.saved,
         "created_at": l.created_at.isoformat() if l.created_at else None,
         "updated_at": l.updated_at.isoformat() if l.updated_at else None,
         "products": {"name": product.name, "category": product.category} if product else None}
    if with_result:
        d["result"] = l.result_json
    return d


def _owned_listing(listing_id: str, user: User, db: Session) -> GrowthListing:
    l = db.get(GrowthListing, listing_id)
    if l is None or l.user_id != user.id:
        raise HTTPException(404, "Listing not found.")
    return l


# --- products ----------------------------------------------------------------

@router.post("/products")
def create_product(body: ProductCreate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = Product(user_id=user.id, name=body.name.strip(), category=body.category,
                style=body.style, target_audience=body.target_audience, notes=body.notes)
    db.add(p)
    db.commit()
    return _product_dict(p)


@router.get("/products")
def list_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Product).filter(Product.user_id == user.id)
            .order_by(Product.created_at.desc()).all())
    return [_product_dict(p) for p in rows]


# --- generation ---------------------------------------------------------------

@router.post("/generate")
def generate(body: GenerateBody, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    product = db.get(Product, body.product_id)
    if product is None or product.user_id != user.id:
        raise HTTPException(404, "Product not found.")
    ok, quota = check_quota(db, user)
    if not ok:
        raise HTTPException(402, f"Monthly listing quota reached ({quota['used']}/{quota['limit']}). Upgrade to continue.")

    try:
        result, usage = elevate.generate(product, body.competitors, body.keywords)
    except Exception as exc:
        raise HTTPException(502, f"The AI engine had trouble generating this listing: {exc}")

    listing = GrowthListing(
        user_id=user.id, product_id=product.id,
        title=result.titles.best[:200] or product.name,
        status="generated", score=result.scores.overall,
        result_json=result.model_dump(mode="json"))
    db.add(listing)
    db.commit()
    record_usage(db, user, listing.id, usage)
    return {"listing_id": listing.id, "result": listing.result_json}


@router.post("/listings/{listing_id}/improve")
def improve(listing_id: str, body: ImproveBody,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = _owned_listing(listing_id, user, db)
    product = db.get(Product, listing.product_id) if listing.product_id else None
    if product is None:
        product = SimpleNamespace(name=listing.title, category=None, style=None,
                                  target_audience=None, notes=None, files=[])
    try:
        result, usage = elevate.improve(product, listing.result_json,
                                        body.action, body.instruction)
    except Exception as exc:
        raise HTTPException(502, f"Improvement failed: {exc}")

    listing.title = result.titles.best[:200] or listing.title
    listing.score = result.scores.overall
    listing.result_json = result.model_dump(mode="json")
    db.commit()
    record_usage(db, user, listing.id, usage)
    return {"listing_id": listing.id, "result": listing.result_json}


# --- listings -----------------------------------------------------------------

@router.get("/listings")
def list_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(GrowthListing).filter(GrowthListing.user_id == user.id)
            .order_by(GrowthListing.created_at.desc()).all())
    products = {p.id: p for p in db.query(Product).filter(Product.user_id == user.id).all()}
    return [_listing_dict(l, products.get(l.product_id)) for l in rows]


@router.get("/listings/{listing_id}")
def get_listing(listing_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    l = _owned_listing(listing_id, user, db)
    product = db.get(Product, l.product_id) if l.product_id else None
    return _listing_dict(l, product)


@router.delete("/listings/{listing_id}")
def delete_listing(listing_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    l = _owned_listing(listing_id, user, db)
    db.delete(l)
    db.commit()
    return {"ok": True}


# --- profile ------------------------------------------------------------------

@router.get("/profile")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    return {"display_name": p.display_name if p else None,
            "brand_name": p.brand_name if p else None}


@router.patch("/profile")
def update_profile(body: ProfileBody, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    if p is None:
        p = Profile(user_id=user.id)
        db.add(p)
    p.display_name = body.display_name
    p.brand_name = body.brand_name
    db.commit()
    return {"display_name": p.display_name, "brand_name": p.brand_name}
