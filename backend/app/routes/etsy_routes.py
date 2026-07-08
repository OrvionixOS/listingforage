import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import (EtsyConnection, Listing, ListingMetric,
                        PublishedListing, User, get_db)
from ..etsy import optimizer
from ..etsy.client import EtsyClient
from ..etsy.publisher import DEFAULT_TAXONOMY, pre_publish_gate, publish_listing
from ..notify import notify_publish
from ..schemas import ListingOutput

log = logging.getLogger("listingforge.etsy")
router = APIRouter(prefix="/api/etsy", tags=["etsy"])


def _connection(db: Session, user: User) -> EtsyConnection:
    conn = db.query(EtsyConnection).filter(EtsyConnection.user_id == user.id).first()
    if conn is None or not conn.access_token:
        raise HTTPException(409, "Etsy shop not connected. Start at /api/etsy/connect.")
    return conn


@router.get("/connect")
def connect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    client = EtsyClient()
    if not client.api_key:
        raise HTTPException(501, "Etsy integration not configured: set ETSY_API_KEY and ETSY_REDIRECT_URI.")
    url, state, verifier = client.build_connect_url()
    conn = db.query(EtsyConnection).filter(EtsyConnection.user_id == user.id).first()
    if conn is None:
        conn = EtsyConnection(user_id=user.id)
        db.add(conn)
    conn.oauth_state, conn.code_verifier = state, verifier
    db.commit()
    return {"authorize_url": url}


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    conn = db.query(EtsyConnection).filter(EtsyConnection.oauth_state == state).first()
    if conn is None:
        raise HTTPException(400, "Unknown or expired OAuth state.")
    client = EtsyClient()
    tokens = client.exchange_code(code, conn.code_verifier)
    conn.access_token = tokens["access_token"]
    conn.refresh_token = tokens.get("refresh_token")
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(tokens.get("expires_in", 3600)))
    conn.oauth_state = conn.code_verifier = None
    # resolve shop
    me = client.get_me(conn.access_token)
    conn.shop_id = str(me.get("shop_id") or "")
    if not conn.shop_id:
        shops = client.get_shop(conn.access_token, me.get("user_id"))
        results = shops.get("results", [])
        if results:
            conn.shop_id = str(results[0]["shop_id"])
            conn.shop_name = results[0].get("shop_name")
    db.commit()
    return RedirectResponse("/?etsy=connected")


@router.get("/status")
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = db.query(EtsyConnection).filter(EtsyConnection.user_id == user.id).first()
    connected = bool(conn and conn.access_token and conn.shop_id)
    return {"connected": connected,
            "shop_id": conn.shop_id if connected else None,
            "shop_name": conn.shop_name if connected else None,
            "configured": bool(EtsyClient().api_key)}


@router.get("/listings/{listing_id}/gate")
def check_gate(listing_id: str, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Run the pre-publish gate without publishing — powers the UI checklist."""
    from ..database import ListingImage
    listing = db.get(Listing, listing_id)
    if listing is None or listing.user_id != user.id:
        raise HTTPException(404, "Listing not found.")
    if listing.status != "complete" or not listing.output_json:
        raise HTTPException(409, "Listing generation is not complete.")
    output = ListingOutput.model_validate(listing.output_json)
    images = (db.query(ListingImage)
              .filter(ListingImage.listing_id == listing.id,
                      ListingImage.superseded.is_(False)).all())
    gate = pre_publish_gate(output, images,
                            DEFAULT_TAXONOMY[output.product_category])
    return {"ok": gate.ok, "blocks": gate.blocks,
            "default_taxonomy_id": DEFAULT_TAXONOMY[output.product_category]}


@router.post("/listings/{listing_id}/publish")
def publish(listing_id: str, body: dict,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.user_id != user.id:
        raise HTTPException(404, "Listing not found.")
    if listing.status != "complete":
        raise HTTPException(409, "Listing generation is not complete.")
    conn = _connection(db, user)
    price = body.get("price") or listing.input_price
    if not price or price <= 0:
        raise HTTPException(400, "A positive price is required to publish.")
    try:
        record = publish_listing(
            db, listing, conn, price=float(price),
            taxonomy_id=body.get("taxonomy_id"),
            shipping_profile_id=body.get("shipping_profile_id"),
            activate=bool(body.get("activate", False)))
    except ValueError as exc:
        notify_publish(db, user.id, listing_id, ok=False, error=str(exc))
        raise HTTPException(422, str(exc))
    notify_publish(db, user.id, listing_id, ok=True, etsy_url=record.etsy_url)
    return {"etsy_listing_id": record.etsy_listing_id,
            "etsy_url": record.etsy_url, "state": record.state}


@router.post("/metrics/sync")
def metrics_sync(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = _connection(db, user)
    n = optimizer.sync_metrics(db, conn)
    return {"synced": n}


@router.get("/metrics")
def metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (db.query(PublishedListing, ListingMetric)
            .join(ListingMetric, ListingMetric.published_listing_id == PublishedListing.id)
            .filter(PublishedListing.user_id == user.id)
            .order_by(ListingMetric.captured_at.desc()).limit(100).all())
    return [{"etsy_listing_id": p.etsy_listing_id, "etsy_url": p.etsy_url,
             "state": p.state, "views": m.views, "favorites": m.favorites,
             "favorite_rate": m.ctr_proxy, "captured_at": m.captured_at.isoformat()}
            for p, m in rows]


@router.get("/listings/{listing_id}/competitive")
def competitive(listing_id: str, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if listing is None or listing.user_id != user.id:
        raise HTTPException(404, "Listing not found.")
    if listing.status != "complete":
        raise HTTPException(409, "Listing generation is not complete.")
    conn = _connection(db, user)
    return optimizer.analyze(db, listing, conn)
