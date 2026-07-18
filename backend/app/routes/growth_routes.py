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

from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import elevate, listing_images
from ..auth import get_current_user
from ..billing import check_quota, record_usage
from ..database import GrowthListing, Product, Profile, Upload, User, get_db
from ..storage import storage

router = APIRouter(prefix="/api/growth", tags=["growth"])


class ProductCreate(BaseModel):
    # Minimal-question intake: everything optional except the images —
    # the product itself provides the information.
    name: str | None = Field(default=None, max_length=300)
    category: str | None = None
    style: str | None = None
    target_audience: str | None = None
    notes: str | None = None
    brand_name: str | None = None
    color_preferences: str | None = None
    file_link: str | None = None
    upload_ids: list[str] = Field(default_factory=list)
    asset_upload_ids: list[str] = Field(default_factory=list)


class IdentifyBody(BaseModel):
    upload_ids: list[str] = Field(min_length=1)


class GenerateBody(BaseModel):
    product_id: str
    competitors: str = ""
    keywords: str = ""


class ImproveBody(BaseModel):
    action: str
    instruction: str = ""


class BeatCompetitorBody(BaseModel):
    product_id: str
    competitor_url: str = Field(min_length=8)


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


# --- uploads + vision identification ------------------------------------------

def _owned_uploads(upload_ids: list[str], user: User, db: Session) -> list[Upload]:
    rows = (db.query(Upload)
            .filter(Upload.user_id == user.id, Upload.id.in_(upload_ids)).all())
    if not rows:
        raise HTTPException(400, "Upload your product images first.")
    return rows


@router.post("/uploads")
async def upload_image(file: UploadFile, kind: str = "image",
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """kind=image (default): product images. kind=asset: the product file
    itself (PDF / ZIP / SVG) so the AI can read what's actually included."""
    try:
        upload_id, path = await storage.save_upload(user.id, file,
                                                    allow_assets=(kind == "asset"))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.add(Upload(id=upload_id, user_id=user.id, filename=file.filename or "upload",
                  content_type=file.content_type or "image/png", path=path))
    db.commit()
    return {"upload_id": upload_id, "filename": file.filename, "kind": kind}


@router.post("/identify")
def identify(body: IdentifyBody, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """Vision pass over the uploaded images: what IS this product, how to
    position it, plus a ready SEO title, 13 tags and collection branding."""
    uploads = _owned_uploads(body.upload_ids, user, db)
    try:
        result, usage = elevate.identify_product([u.path for u in uploads])
    except Exception as exc:
        raise HTTPException(502, f"Image analysis failed: {exc}")
    return result.model_dump(mode="json")


# --- products ----------------------------------------------------------------

@router.post("/products")
def create_product(body: ProductCreate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    files = []
    if body.upload_ids:
        files += [{"upload_id": u.id, "name": u.filename, "type": u.content_type,
                   "path": u.path, "size": 0, "kind": "image"}
                  for u in _owned_uploads(body.upload_ids, user, db)]
    if body.asset_upload_ids:
        files += [{"upload_id": u.id, "name": u.filename, "type": u.content_type,
                   "path": u.path, "size": 0, "kind": "asset"}
                  for u in _owned_uploads(body.asset_upload_ids, user, db)]
    p = Product(user_id=user.id,
                name=(body.name or "").strip() or "Untitled product",
                category=body.category, style=body.style,
                target_audience=body.target_audience, notes=body.notes,
                brand_name=body.brand_name, color_preferences=body.color_preferences,
                file_link=body.file_link, files=files)
    db.add(p)
    db.commit()
    return _product_dict(p)


@router.get("/products")
def list_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Product).filter(Product.user_id == user.id)
            .order_by(Product.created_at.desc()).all())
    return [_product_dict(p) for p in rows]


def _product_image_paths(product) -> list[str]:
    return [f["path"] for f in (getattr(product, "files", None) or [])
            if isinstance(f, dict) and f.get("path") and f.get("kind") != "asset"]


def _render_gallery(listing: GrowthListing, product, db: Session) -> None:
    """Render the 10 finished listing images from the seller's product images
    + brand palette, store them, and record their served URLs on the result.
    Never fatal — a render failure leaves the image plan intact."""
    try:
        out_dir = f"{storage.root}/generated/{listing.id}"
        meta = listing_images.render_gallery(
            listing.result_json, _product_image_paths(product), out_dir,
            listing_id=listing.id, style=getattr(product, "style", "") or "")
        for m in meta:
            m["url"] = f"/api/growth/listings/{listing.id}/gallery/{m['n']}"
        merged = dict(listing.result_json or {})
        merged["renderedImages"] = meta
        listing.result_json = merged
        db.commit()
    except Exception:
        import logging
        logging.getLogger("listingforge.api").exception("gallery render failed")


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
    # minimal-question flow: if the seller never named the product, the AI did
    if product.name == "Untitled product":
        product.name = result.titles.best[:120]
    db.commit()
    record_usage(db, user, listing.id, usage)
    _render_gallery(listing, product, db)
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
    _render_gallery(listing, product, db)
    return {"listing_id": listing.id, "result": listing.result_json}


# --- Growth Lab: thumbnails, upgrades, expansion, beat-competitor, package -----

def _product_for(listing: GrowthListing, db: Session):
    product = db.get(Product, listing.product_id) if listing.product_id else None
    if product is None:
        product = SimpleNamespace(name=listing.title, category=None, style=None,
                                  target_audience=None, notes=None, files=[],
                                  brand_name=None, color_preferences=None, file_link=None)
    return product


def _merge_result(db: Session, listing: GrowthListing, key: str, value: dict) -> None:
    """Persist a Growth Lab result alongside the ListingResult (JSON column
    needs reassignment, not mutation, to be detected)."""
    merged = dict(listing.result_json or {})
    merged[key] = value
    listing.result_json = merged
    db.commit()


@router.post("/listings/{listing_id}/thumbnails")
def thumbnails(listing_id: str, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    listing = _owned_listing(listing_id, user, db)
    try:
        sim, usage = elevate.thumbnail_simulation(_product_for(listing, db), listing.result_json)
    except Exception as exc:
        raise HTTPException(502, f"Thumbnail simulation failed: {exc}")
    data = sim.model_dump(mode="json")
    _merge_result(db, listing, "thumbnailSimulation", data)
    record_usage(db, user, listing.id, usage)
    return data


@router.post("/listings/{listing_id}/upgrades")
def upgrades(listing_id: str, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    listing = _owned_listing(listing_id, user, db)
    try:
        plan, usage = elevate.upgrade_plan(_product_for(listing, db), listing.result_json)
    except Exception as exc:
        raise HTTPException(502, f"Upgrade generation failed: {exc}")
    data = plan.model_dump(mode="json")
    _merge_result(db, listing, "upgradePlan", data)
    record_usage(db, user, listing.id, usage)
    return data


@router.post("/listings/{listing_id}/expansion")
def expansion(listing_id: str, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    listing = _owned_listing(listing_id, user, db)
    try:
        plan, usage = elevate.expansion_plan(_product_for(listing, db), listing.result_json)
    except Exception as exc:
        raise HTTPException(502, f"Expansion planning failed: {exc}")
    data = plan.model_dump(mode="json")
    _merge_result(db, listing, "expansionPlan", data)
    record_usage(db, user, listing.id, usage)
    return data


@router.post("/beat-competitor")
def beat_competitor(body: BeatCompetitorBody, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Paste a competitor Etsy listing URL → live teardown → the seller's
    entire listing rebuilt to outperform it. Creates a NEW listing."""
    product = db.get(Product, body.product_id)
    if product is None or product.user_id != user.id:
        raise HTTPException(404, "Product not found.")
    ok, quota = check_quota(db, user)
    if not ok:
        raise HTTPException(402, f"Monthly listing quota reached ({quota['used']}/{quota['limit']}). Upgrade to continue.")
    try:
        teardown, result, usage = elevate.beat_competitor(product, body.competitor_url)
    except Exception as exc:
        raise HTTPException(502, f"Beat-competitor run failed: {exc}")

    merged = result.model_dump(mode="json")
    merged["competitorTeardown"] = teardown.model_dump(mode="json")
    merged["competitorTeardown"]["competitor_url"] = body.competitor_url
    listing = GrowthListing(
        user_id=user.id, product_id=product.id,
        title=result.titles.best[:200] or product.name,
        status="generated", score=result.scores.overall, result_json=merged)
    db.add(listing)
    db.commit()
    record_usage(db, user, listing.id, usage)
    _render_gallery(listing, product, db)
    return {"listing_id": listing.id, "teardown": merged["competitorTeardown"],
            "result": listing.result_json}


@router.get("/listings/{listing_id}/package")
def listing_package(listing_id: str, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """One-click Etsy listing package: everything ready to upload, as text."""
    listing = _owned_listing(listing_id, user, db)
    return {"package": elevate.build_package(_product_for(listing, db), listing.result_json)}


# --- rendered listing images: serve files, re-render, download all ------------

@router.get("/listings/{listing_id}/gallery/{n}")
def gallery_image(listing_id: str, n: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    listing = _owned_listing(listing_id, user, db)
    path = Path(f"{storage.root}/generated/{listing.id}/image_{n:02d}.png")
    if not path.exists():
        raise HTTPException(404, "Image not rendered.")
    return FileResponse(str(path), media_type="image/png",
                        filename=f"etsy-image-{n:02d}.png")


@router.post("/listings/{listing_id}/render")
def render_gallery(listing_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """(Re)render the 10 listing images — e.g. after editing the brand palette."""
    listing = _owned_listing(listing_id, user, db)
    _render_gallery(listing, _product_for(listing, db), db)
    return {"rendered": (listing.result_json or {}).get("renderedImages", [])}


@router.get("/listings/{listing_id}/gallery.zip")
def gallery_zip(listing_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    import io
    import zipfile

    from fastapi.responses import StreamingResponse
    listing = _owned_listing(listing_id, user, db)
    gdir = Path(f"{storage.root}/generated/{listing.id}")
    if not gdir.exists():
        raise HTTPException(404, "No rendered images yet.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(gdir.glob("image_*.png")):
            z.write(p, p.name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="etsy-listing-images-{listing_id[:8]}.zip"'})


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


# --- Etsy connection diagnostic -----------------------------------------------

@router.get("/etsy-check")
def etsy_check(user: User = Depends(get_current_user)):
    """Live Etsy credential test: makes one real API call and returns exactly
    what Etsy answered, so key problems stop being guesswork."""
    from ..etsy.client import EtsyAPIError, EtsyClient
    client = EtsyClient()
    if not client.api_key:
        return {"configured": False, "ok": False,
                "detail": "ETSY_API_KEY is not set on the server."}
    info = {"configured": True, "key_length": len(client.api_key)}
    try:
        rows = client.search_active_public("digital download", limit=1)
        return {**info, "ok": True,
                "detail": f"Etsy accepted the key — search returned {len(rows)} result(s). "
                          "Live market data is active."}
    except EtsyAPIError as exc:
        hint = ""
        if exc.status == 403:
            hint = (" Hint: a 403 with a correct, approved keystring usually means the app's "
                    "credentials are not enabled for Open API v3 — in the Etsy developer portal "
                    "check that this app shows 'Open API v3' access (legacy v2-era apps need a "
                    "v3-enabled app / new keystring).")
        return {**info, "ok": False, "status": exc.status, "detail": str(exc) + hint}
    except Exception as exc:
        return {**info, "ok": False, "detail": f"Request failed before reaching Etsy: {exc}"}


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
