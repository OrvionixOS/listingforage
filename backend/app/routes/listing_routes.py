import logging

from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException,
                     UploadFile)
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..billing import check_quota, record_usage
from ..database import Listing, SessionLocal, Upload, User, get_db
from ..brandctx import brand_context
from ..etsy.optimizer import performance_context
from ..notify import notify_generation, notify_low_credits
from ..pipeline.orchestrator import generate_listing
from ..schemas import GenerateRequest
from ..storage import storage

log = logging.getLogger("listingforge.api")
router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.post("/uploads")
async def upload_image(file: UploadFile, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    try:
        upload_id, path = await storage.save_upload(user.id, file)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    record = Upload(id=upload_id, user_id=user.id, filename=file.filename or "upload",
                    content_type=file.content_type, path=path)
    db.add(record)
    db.commit()
    return {"upload_id": upload_id, "filename": record.filename}


@router.post("/intake/analyze")
def intake_analyze(body: dict, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Photos-first intake: analyze uploads, come back with what we already
    know so the wizard only asks what the pixels can't answer."""
    from ..database import BrandProfile
    from ..imaging.vision_analyzer import analyze_product_images

    ids = body.get("image_ids", [])
    uploads = (db.query(Upload)
               .filter(Upload.user_id == user.id, Upload.id.in_(ids)).all())
    if not uploads:
        raise HTTPException(400, "Upload at least one product file first.")
    # Digital packs can be 100+ files; palette/quality are consistent across a
    # pack, so analyze an evenly-spaced sample and report the true total.
    SAMPLE = 12
    image_paths = [u.path for u in uploads
                   if u.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))]
    step = max(1, len(image_paths) // SAMPLE)
    sampled = image_paths[::step][:SAMPLE]
    report = analyze_product_images(sampled)
    report["total_files"] = len(uploads)
    report["analyzed_sample"] = len(sampled)

    agg = report.get("aggregate", {})
    sem = agg.get("semantic", {})
    profile = db.query(BrandProfile).filter(BrandProfile.user_id == user.id).first()
    brand_configured = bool(profile and (profile.voice or profile.messaging_pillars))
    warnings = [f"Photo issue: {d}" for d in agg.get("all_defects", [])][:4]

    return {
        "vision": report,
        "suggested": {
            "category_guess": sem.get("product_category_guess", ""),
            "materials_guess": sem.get("materials_guess", []),
            "palette": agg.get("dominant_palette", []),
        },
        "brand_configured": brand_configured,
        "brand_name": profile.brand_name if brand_configured else "",
        "photo_warnings": warnings,
    }


def _vision_context(image_paths: list[str]) -> str:
    """Pixel truths about the actual product photos, for the BDE."""
    if not image_paths:
        return ""
    try:
        from ..imaging.vision_analyzer import analyze_product_images
        imgs = [p for p in image_paths
                if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))]
        step = max(1, len(imgs) // 12)
        r = analyze_product_images(imgs[::step][:12], use_semantic=False)
        agg = r.get("aggregate", {})
        lines = ["PRODUCT PHOTO ANALYSIS (measured from the seller's uploads):",
                 f"- {r['image_count']} photo(s), {agg.get('clean_images', 0)} clean",
                 f"- dominant colors: {', '.join(agg.get('dominant_palette', [])[:3])}",
                 f"- avg sharpness {agg.get('avg_sharpness')} / background uniformity "
                 f"{agg.get('avg_background_uniformity')}"]
        if agg.get("all_defects"):
            lines.append("- issues to compensate for in image strategy: "
                         + "; ".join(agg["all_defects"][:3]))
        return "\n".join(lines)
    except Exception:
        log.warning("vision context failed", exc_info=True)
        return ""


def _run_pipeline(listing_id: str, user_id: str, req: GenerateRequest, image_paths: list[str]):
    """Background worker: owns its own DB session."""
    db = SessionLocal()
    try:
        listing = db.get(Listing, listing_id)
        user = db.get(User, user_id)
        if listing.status != "generating":
            listing.status = "generating"
            db.commit()

        def on_step(name, index, total):
            step_db = SessionLocal()
            try:
                row = step_db.get(Listing, listing_id)
                row.progress_json = {"step": name, "index": index, "total": total}
                step_db.commit()
            finally:
                step_db.close()

        try:
            perf_ctx = performance_context(db, user_id)
            result = generate_listing(
                title=req.title, description=req.description,
                price=req.price, notes=req.notes, image_paths=image_paths,
                db=db, listing_id=listing_id, performance_context=perf_ctx,
                brand_context=brand_context(db, user_id),
                vision_context=_vision_context(image_paths), on_step=on_step,
            )
            listing.output_json = result.output.model_dump(mode="json")
            listing.category = result.output.classification.category.value
            listing.status = "complete"
            listing.progress_json = {"step": "done", "index": 11, "total": 11}
            db.commit()
            record_usage(db, user, listing_id, result.usage)
            notify_generation(db, user_id, listing_id, listing.title, ok=True)
            from ..billing import check_quota
            ok_q, quota = check_quota(db, user)
            if quota["limit"] and quota["remaining"] <= max(1, quota["limit"] // 10):
                notify_low_credits(db, user_id, quota["remaining"], quota["limit"])
        except Exception as exc:
            log.exception("pipeline failed for listing %s", listing_id)
            listing.status = "failed"
            listing.error = str(exc)
            db.commit()
            notify_generation(db, user_id, listing_id, listing.title, ok=False, error=str(exc))
    finally:
        db.close()


@router.post("/generate")
def generate(req: GenerateRequest, background: BackgroundTasks,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ok, quota = check_quota(db, user)
    if not ok:
        raise HTTPException(402, f"Monthly listing quota reached ({quota['limit']}). Upgrade to continue.")

    uploads = (db.query(Upload)
               .filter(Upload.user_id == user.id, Upload.id.in_(req.image_ids))
               .all()) if req.image_ids else []
    image_paths = [u.path for u in uploads]

    listing = Listing(user_id=user.id, title=req.title,
                      input_description=req.description,
                      input_price=req.price, input_notes=req.notes,
                      status="generating")
    db.add(listing)
    db.commit()
    for u in uploads:
        u.listing_id = listing.id
    db.commit()

    from ..jobs import enqueue
    enqueue(db, user.id, "generate_listing",
            {"listing_id": listing.id, "req": req.model_dump(mode="json"),
             "image_paths": image_paths})
    return {"listing_id": listing.id, "status": "generating", "quota": quota}


@router.get("")
def list_listings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(Listing).filter(Listing.user_id == user.id)
            .order_by(Listing.created_at.desc()).limit(100).all())
    return [{
        "id": r.id, "title": r.title, "status": r.status,
        "category": r.category, "created_at": r.created_at.isoformat(),
    } for r in rows]


def _get_owned(listing_id: str, user: User, db: Session) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None or listing.user_id != user.id:
        raise HTTPException(404, "Listing not found.")
    return listing


@router.get("/{listing_id}")
def get_listing(listing_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    r = _get_owned(listing_id, user, db)
    return {
        "id": r.id, "title": r.title, "status": r.status, "error": r.error,
        "category": r.category, "output": r.output_json,
        "progress": r.progress_json, "input_price": r.input_price,
        "created_at": r.created_at.isoformat(),
    }


@router.patch("/{listing_id}")
def update_listing(listing_id: str, body: dict,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Allow the seller to edit generated output (title picks, copy tweaks)."""
    r = _get_owned(listing_id, user, db)
    if "output" in body and isinstance(body["output"], dict):
        r.output_json = body["output"]
    if "title" in body:
        r.title = body["title"]
    db.commit()
    return {"ok": True}


@router.delete("/{listing_id}")
def delete_listing(listing_id: str, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    r = _get_owned(listing_id, user, db)
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.get("/{listing_id}/export/{fmt}", response_class=PlainTextResponse)
def export_listing(listing_id: str, fmt: str,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = _get_owned(listing_id, user, db)
    if r.status != "complete" or not r.output_json:
        raise HTTPException(409, "Listing generation is not complete.")
    formats = r.output_json.get("export_formats", {})
    key = {"etsy": "etsy_paste_ready", "csv": "csv_row", "images": "image_brief", "scorecard": "scorecard"}.get(fmt)
    if key is None or key not in formats:
        raise HTTPException(404, f"Unknown export format '{fmt}'. Use: etsy, csv, images, scorecard.")
    return formats[key]


# ---------------------------------------------------------------------------
# Generated images: metadata, file serving, per-slot regeneration, logs
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse

from ..database import ImageGenerationLog, ListingImage


@router.get("/{listing_id}/images")
def list_images(listing_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    _get_owned(listing_id, user, db)
    rows = (db.query(ListingImage)
            .filter(ListingImage.listing_id == listing_id,
                    ListingImage.superseded.is_(False))
            .order_by(ListingImage.display_order).all())
    return [{"slot_id": r.slot_id, "display_order": r.display_order,
             "final_image_url": f"/api/listings/{listing_id}/images/{r.slot_id}/file",
             "generation_prompt": r.prompt_used, "style_profile": r.style_profile,
             "validation_score": r.validation_score, "scores": r.score_json,
             "regeneration_count": r.regeneration_count, "provider": r.provider}
            for r in rows]


@router.get("/{listing_id}/images/{slot_id}/file")
def image_file(listing_id: str, slot_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned(listing_id, user, db)
    row = (db.query(ListingImage)
           .filter(ListingImage.listing_id == listing_id,
                   ListingImage.slot_id == slot_id,
                   ListingImage.superseded.is_(False)).first())
    if row is None:
        raise HTTPException(404, "No generated image for this slot yet.")
    return FileResponse(row.image_url, media_type="image/png")


@router.post("/{listing_id}/images/{slot_id}/regenerate")
def regenerate_image(listing_id: str, slot_id: int,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from pathlib import Path

    from ..config import get_settings
    from ..imaging.generator import generate_slot
    from ..imaging.providers import get_provider
    from ..schemas import ListingOutput

    listing = _get_owned(listing_id, user, db)
    if listing.status != "complete" or not listing.output_json:
        raise HTTPException(409, "Listing generation is not complete.")
    output = ListingOutput.model_validate(listing.output_json)
    slot = next((s for s in output.image_prompts.slots if s.slot_id == slot_id), None)
    if slot is None:
        raise HTTPException(404, f"No strategy slot {slot_id}.")
    out_dir = Path(get_settings().storage_dir) / "generated" / listing_id
    result = generate_slot(db, listing_id, slot, get_provider(), out_dir)
    return {"slot_id": result.slot_id, "validation_score": result.validation_score,
            "scores": result.scores, "regeneration_count": result.regeneration_count}


@router.get("/{listing_id}/images/{slot_id}/logs")
def image_logs(listing_id: str, slot_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned(listing_id, user, db)
    rows = (db.query(ImageGenerationLog)
            .filter(ImageGenerationLog.listing_id == listing_id,
                    ImageGenerationLog.slot_id == slot_id)
            .order_by(ImageGenerationLog.timestamp).all())
    return [{"attempt": r.attempt_number, "passed": r.passed,
             "failure_reason": r.failure_reason, "scores": r.score_json,
             "timestamp": r.timestamp.isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# Phase 4: editor, quality panel, SEO studio, journey simulator, exports,
# image studio operations
# ---------------------------------------------------------------------------
from fastapi.responses import Response

from .. import editor as editor_engine
from .. import exporter, insights


def _complete(listing_id: str, user: User, db: Session) -> Listing:
    listing = _get_owned(listing_id, user, db)
    if listing.status != "complete" or not listing.output_json:
        raise HTTPException(409, "Listing generation is not complete.")
    return listing


@router.patch("/{listing_id}")
def edit_listing(listing_id: str, body: dict,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = _complete(listing_id, user, db)
    result = editor_engine.apply_edits(db, listing, body)
    if not result.ok:
        raise HTTPException(422, "; ".join(result.errors))
    return {"ok": True, "scores": result.scores}


ASSIST_MULTIPLIER = 5  # assist calls allowed per cycle = 5x listing quota


@router.post("/{listing_id}/assist")
def assist_field(listing_id: str, body: dict,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone

    from ..billing import PLANS
    from ..database import ListingEvent

    listing = _complete(listing_id, user, db)
    field_name = body.get("field")
    if field_name not in ("title", "description_block", "tags"):
        raise HTTPException(400, "field must be title, description_block, or tags.")

    # Quota: AI assist is metered (it makes a real model call per click).
    plan = PLANS.get(user.plan, PLANS["free"])
    limit = plan["listings_per_month"] * ASSIST_MULTIPLIER
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    used = (db.query(ListingEvent)
            .filter(ListingEvent.user_id == user.id,
                    ListingEvent.kind == "assist",
                    ListingEvent.created_at >= since).count())
    if limit and used >= limit:
        raise HTTPException(402, f"AI assist limit reached ({limit} per cycle "
                                 f"on the {user.plan} plan).")
    try:
        result = editor_engine.assist(listing, field_name,
                                      instruction=str(body.get("instruction", ""))[:500],
                                      block_index=body.get("block_index"))
    except Exception as exc:
        raise HTTPException(502, f"AI assist unavailable: {exc}")
    db.add(ListingEvent(user_id=user.id, listing_id=listing_id, kind="assist",
                        payload={"field": field_name}))
    db.commit()
    result["assist_used"] = used + 1
    result["assist_limit"] = limit
    return result


@router.get("/{listing_id}/quality")
def quality(listing_id: str, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    listing = _complete(listing_id, user, db)
    return editor_engine.rescore(db, listing)


@router.get("/{listing_id}/seo")
def seo(listing_id: str, user: User = Depends(get_current_user),
        db: Session = Depends(get_db)):
    listing = _complete(listing_id, user, db)
    return insights.seo_report(db, listing)


@router.get("/{listing_id}/journey")
def buyer_journey(listing_id: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    listing = _complete(listing_id, user, db)
    return insights.journey(db, listing)


@router.get("/{listing_id}/export/{fmt}")
def export_file(listing_id: str, fmt: str,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = _complete(listing_id, user, db)
    safe = "".join(c for c in listing.title[:40] if c.isalnum() or c in " -_").strip() or "listing"
    if fmt == "json":
        return Response(exporter.listing_json(listing), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{safe}.json"'})
    if fmt == "csv":
        return Response(exporter.listing_csv(listing), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{safe}.csv"'})
    if fmt == "pdf":
        return Response(exporter.pdf_report(db, listing), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{safe}-report.pdf"'})
    if fmt == "zip":
        return Response(exporter.asset_zip(db, listing), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{safe}-assets.zip"'})
    raise HTTPException(400, "fmt must be json, csv, pdf, or zip.")


@router.post("/{listing_id}/images/reorder")
def reorder_images(listing_id: str, body: dict,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _complete(listing_id, user, db)
    order = body.get("order", [])
    positions = sorted(item.get("display_order") for item in order)
    if positions != list(range(1, len(order) + 1)):
        raise HTTPException(422, "display_order values must be a permutation of 1..N.")
    live = {r.slot_id: r for r in db.query(ListingImage).filter(
        ListingImage.listing_id == listing_id, ListingImage.superseded.is_(False)).all()}
    if {item.get("slot_id") for item in order} != set(live):
        raise HTTPException(422, "order must cover exactly the live slots.")
    for item in order:
        live[item["slot_id"]].display_order = item["display_order"]
    db.commit()
    return {"ok": True}


@router.get("/{listing_id}/images/{slot_id}/versions")
def image_versions(listing_id: str, slot_id: int,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned(listing_id, user, db)
    rows = (db.query(ListingImage)
            .filter(ListingImage.listing_id == listing_id,
                    ListingImage.slot_id == slot_id)
            .order_by(ListingImage.created_at.desc()).all())
    return [{"image_id": r.id, "live": not r.superseded,
             "validation_score": r.validation_score, "scores": r.score_json,
             "regeneration_count": r.regeneration_count,
             "created_at": r.created_at.isoformat(),
             "file_url": f"/api/listings/{listing_id}/images/{slot_id}/versions/{r.id}/file"}
            for r in rows]


@router.get("/{listing_id}/images/{slot_id}/versions/{image_id}/file")
def image_version_file(listing_id: str, slot_id: int, image_id: str,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_owned(listing_id, user, db)
    row = db.get(ListingImage, image_id)
    if row is None or row.listing_id != listing_id:
        raise HTTPException(404, "Version not found.")
    return FileResponse(row.image_url, media_type="image/png")


@router.post("/{listing_id}/images/{slot_id}/restore/{image_id}")
def restore_version(listing_id: str, slot_id: int, image_id: str,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _complete(listing_id, user, db)
    target = db.get(ListingImage, image_id)
    if target is None or target.listing_id != listing_id or target.slot_id != slot_id:
        raise HTTPException(404, "Version not found.")
    current = (db.query(ListingImage)
               .filter(ListingImage.listing_id == listing_id,
                       ListingImage.slot_id == slot_id,
                       ListingImage.superseded.is_(False)).first())
    if current is not None and current.id != target.id:
        target.display_order = current.display_order
        current.superseded = True
    target.superseded = False
    db.commit()
    return {"ok": True, "live_image_id": target.id}


@router.post("/{listing_id}/images/{slot_id}/regenerate_custom")
def regenerate_custom(listing_id: str, slot_id: int, body: dict,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Regenerate with a user-edited prompt — still pixel-validated."""
    from pathlib import Path

    from ..config import get_settings
    from ..imaging.generator import MANDATORY_SUFFIX, STYLE_PROFILES
    from ..imaging.image_validator import score_image
    from ..imaging.providers import get_provider
    from ..schemas import ListingOutput

    listing = _complete(listing_id, user, db)
    custom = str(body.get("prompt", "")).strip()
    if len(custom) < 30:
        raise HTTPException(422, "Custom prompt must be at least 30 characters.")
    output = ListingOutput.model_validate(listing.output_json)
    slot = next((s for s in output.image_prompts.slots if s.slot_id == slot_id), None)
    if slot is None:
        raise HTTPException(404, f"No strategy slot {slot_id}.")
    if MANDATORY_SUFFIX not in custom:
        custom = custom + "\n" + MANDATORY_SUFFIX
    style = STYLE_PROFILES.get(slot.required_visual_type, "hero_contrast")
    out_dir = Path(get_settings().storage_dir) / "generated" / listing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = db.query(ImageGenerationLog).filter_by(
        listing_id=listing_id, slot_id=slot_id).count()
    path = out_dir / f"slot{slot_id}_custom{existing + 1}.png"
    get_provider().generate(custom, style, str(path))
    scores = score_image(str(path), slot.intent)
    db.add(ImageGenerationLog(listing_id=listing_id, slot_id=slot_id,
                              attempt_number=existing + 1, prompt=custom,
                              passed=scores.passed,
                              failure_reason=None if scores.passed else "; ".join(scores.failures),
                              score_json=scores.to_dict()))
    current = (db.query(ListingImage)
               .filter(ListingImage.listing_id == listing_id,
                       ListingImage.slot_id == slot_id,
                       ListingImage.superseded.is_(False)).first())
    record = ListingImage(listing_id=listing_id, slot_id=slot_id, image_url=str(path),
                          prompt_used=custom, style_profile=style,
                          score_json=scores.to_dict(), validation_score=scores.composite,
                          regeneration_count=0, provider=get_provider().name,
                          display_order=current.display_order if current else None)
    if current is not None:
        current.superseded = True
    db.add(record)
    db.commit()
    return {"ok": True, "passed": scores.passed, "failures": scores.failures,
            "validation_score": scores.composite, "scores": scores.to_dict()}
