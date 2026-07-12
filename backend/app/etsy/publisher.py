"""
Etsy Listing Builder + Publisher.

Builds the publish payload from a completed ListingOutput + generated images,
runs the BLOCKING pre-publish gate, creates the draft, uploads all ten gallery
images in the mandated psychological order (display_order → Etsy rank), and
optionally flips the listing to active. Every listing on this platform is a
digital download (type=download, is_digital=True) — there is no physical
fulfillment branch.

BLOCK CONDITIONS (publishing refuses if any hold):
  - fewer than 10 validated images (the full Etsy gallery)
  - missing CTR image
  - missing trust image
  - missing usage context image
  - missing scale/what's-included clarity image
  - invalid/absent Etsy taxonomy id
  - missing or invalid tags
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..database import EtsyConnection, Listing, ListingImage, PublishedListing
from ..schemas import ImageIntent, ListingOutput, ProductCategory
from .client import EtsyClient, token_expired

# Etsy taxonomy ids per digital product category (top-level "Craft Supplies &
# Tools > Digital" defaults; the UI lets sellers refine to a leaf node before
# publishing).
DEFAULT_TAXONOMY = {
    ProductCategory.printable_art: 2078,
    ProductCategory.digital_planner: 2078,
    ProductCategory.template: 2078,
    ProductCategory.invitation: 2078,
    ProductCategory.svg_cut_file: 2078,
    ProductCategory.digital_bundle: 2078,
    ProductCategory.educational_product: 2078,
    ProductCategory.pattern: 2078,
}

WHO_MADE = {"default": "i_did"}


@dataclass
class GateResult:
    ok: bool
    blocks: list[str] = field(default_factory=list)


def pre_publish_gate(output: ListingOutput, images: list[ListingImage],
                     taxonomy_id: int | None) -> GateResult:
    blocks: list[str] = []
    live = [i for i in images if not i.superseded]
    if len(live) < 10:
        blocks.append(f"fewer than 10 images ({len(live)} generated) — the full Etsy gallery is required")

    slot_by_id = {s.slot_id: s for s in output.image_prompts.slots}
    intents = {slot_by_id[i.slot_id].intent for i in live if i.slot_id in slot_by_id}
    visuals = {slot_by_id[i.slot_id].required_visual_type for i in live if i.slot_id in slot_by_id}

    if ImageIntent.CTR not in intents:
        blocks.append("missing CTR image")
    if ImageIntent.TRUST not in intents and not (visuals & {"zoom_proof", "process_shot"}):
        blocks.append("missing trust image")
    if not (visuals & {"lifestyle_scene", "mockup_in_use"}):
        blocks.append("missing usage context image")
    if not (visuals & {"scale_reference", "file_grid", "size_chart", "tiling_demo", "variant_grid"}):
        blocks.append("missing scale clarity image")
    if not taxonomy_id or taxonomy_id <= 0:
        blocks.append("invalid Etsy taxonomy id")
    tags = output.listing_strategy.tags
    if len(tags) != 13 or any(len(t) > 20 or not t.strip() for t in tags):
        blocks.append("missing or invalid tags (need exactly 13, each <=20 chars)")
    return GateResult(ok=not blocks, blocks=blocks)


def build_payload(output: ListingOutput, price: float,
                  taxonomy_id: int | None = None) -> dict:
    listing = output.listing_strategy
    category = output.product_category
    best_title = next((t for t in listing.titles if t.is_best), listing.titles[0])
    description = "\n\n".join(f"{b.heading.upper()}\n{b.body}" for b in listing.description_blocks)
    if listing.faq_items:
        description += "\n\nFAQ\n" + "\n".join(
            f"Q: {f.get('question','')}\nA: {f.get('answer','')}" for f in listing.faq_items)

    payload = {
        "quantity": 999,
        "title": best_title.title,
        "description": description,
        "price": price,
        "who_made": WHO_MADE["default"],
        "when_made": "2020_2026",
        "taxonomy_id": taxonomy_id or DEFAULT_TAXONOMY[category],
        "tags": listing.tags,
        "materials": (listing.materials or output.product_analysis.materials_or_format)[:13],
        "type": "download",
        "is_digital": True,
    }
    return payload


def _fresh_token(db: Session, conn: EtsyConnection, client: EtsyClient) -> str:
    if token_expired(conn.token_expires_at):
        tokens = client.refresh(conn.refresh_token)
        conn.access_token = tokens["access_token"]
        conn.refresh_token = tokens.get("refresh_token", conn.refresh_token)
        conn.token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(tokens.get("expires_in", 3600)))
        db.commit()
    return conn.access_token


def publish_listing(db: Session, listing: Listing, conn: EtsyConnection,
                    price: float, taxonomy_id: int | None = None,
                    shipping_profile_id: int | None = None,
                    activate: bool = False,
                    client: EtsyClient | None = None) -> PublishedListing:
    client = client or EtsyClient()
    output = ListingOutput.model_validate(listing.output_json)
    images = (db.query(ListingImage)
              .filter(ListingImage.listing_id == listing.id,
                      ListingImage.superseded.is_(False))
              .order_by(ListingImage.display_order)
              .all())

    gate = pre_publish_gate(output, images, taxonomy_id or DEFAULT_TAXONOMY[output.product_category])
    if not gate.ok:
        raise ValueError("Publishing blocked: " + "; ".join(gate.blocks))

    token = _fresh_token(db, conn, client)
    payload = build_payload(output, price, taxonomy_id)
    created = client.create_draft_listing(token, conn.shop_id, payload)
    etsy_listing_id = str(created["listing_id"])

    # ordered upload: display_order (psychological sequence) → Etsy rank
    for img in images:
        data = Path(img.image_url).read_bytes()
        client.upload_listing_image(token, conn.shop_id, etsy_listing_id,
                                    data, rank=img.display_order or img.slot_id,
                                    filename=f"slot{img.slot_id}.png")

    state = "draft"
    if activate:
        client.publish(token, conn.shop_id, etsy_listing_id)
        state = "active"

    record = PublishedListing(
        listing_id=listing.id, user_id=listing.user_id,
        etsy_listing_id=etsy_listing_id,
        etsy_url=created.get("url") or f"https://www.etsy.com/listing/{etsy_listing_id}",
        state=state, payload_json=payload,
    )
    db.add(record)
    db.commit()
    return record
