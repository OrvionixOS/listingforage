"""
Export engine — Etsy draft (via publisher), PDF report, CSV, JSON, and a ZIP
package containing every listing asset (images + copy + report).
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from .database import Listing, ListingImage
from .schemas import ListingOutput


def listing_json(listing: Listing) -> bytes:
    return json.dumps(listing.output_json, indent=2).encode()


def listing_csv(listing: Listing) -> bytes:
    output = ListingOutput.model_validate(listing.output_json)
    ls = output.listing_strategy
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["TITLE", "DESCRIPTION", "PRICE", "TAGS", "MATERIALS",
                "CATEGORY", "PRIMARY_KEYWORD"])
    description = "\n\n".join(f"{b.heading.upper()}\n{b.body}" for b in ls.description_blocks)
    w.writerow([ls.titles[0].title, description, listing.input_price or "",
                ",".join(ls.tags), ",".join(output.product_analysis.materials_or_format),
                output.product_category.value, ls.primary_keyword])
    return buf.getvalue().encode()


def etsy_paste(listing: Listing) -> bytes:
    fmt = (listing.output_json or {}).get("export_formats", {})
    return str(fmt.get("etsy_paste_ready", "")).encode()


def pdf_report(db: Session, listing: Listing) -> bytes:
    """One-page-per-section conversion report in the Orvionix aesthetic."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    OBSIDIAN, IVORY, GOLD = HexColor("#0d0d0f"), HexColor("#f4f1ea"), HexColor("#c2a05a")
    output = ListingOutput.model_validate(listing.output_json)
    ls = output.listing_strategy
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    def bg():
        c.setFillColor(OBSIDIAN)
        c.rect(0, 0, W, H, fill=1, stroke=0)

    def h1(text, y):
        c.setFillColor(GOLD); c.setFont("Times-Bold", 22)
        c.drawString(0.9 * inch, y, text)
        c.setStrokeColor(GOLD); c.setLineWidth(0.6)
        c.line(0.9 * inch, y - 8, W - 0.9 * inch, y - 8)
        return y - 34

    def para(text, y, size=10, color=IVORY, max_chars=95, font="Helvetica"):
        c.setFillColor(color); c.setFont(font, size)
        for line in _wrap(text, max_chars):
            if y < 0.8 * inch:
                c.showPage(); bg(); y = H - 1 * inch
                c.setFillColor(color); c.setFont(font, size)
            c.drawString(0.9 * inch, y, line)
            y -= size + 4
        return y

    def _wrap(text, n):
        out = []
        for raw in str(text).split("\n"):
            while len(raw) > n:
                cut = raw.rfind(" ", 0, n)
                cut = cut if cut > 0 else n
                out.append(raw[:cut]); raw = raw[cut:].lstrip()
            out.append(raw)
        return out

    # Cover
    bg()
    c.setFillColor(GOLD); c.setFont("Times-Bold", 30)
    c.drawString(0.9 * inch, H - 1.6 * inch, "ListingForge AI")
    c.setFillColor(IVORY); c.setFont("Helvetica", 11)
    c.drawString(0.9 * inch, H - 1.95 * inch, "CONVERSION INTELLIGENCE REPORT")
    y = para(ls.titles[0].title, H - 2.6 * inch, size=15, color=IVORY, font="Times-Bold", max_chars=60)
    sc = output.conversion_scores
    y -= 18
    for label, val in [("Overall conversion", sc.conversion_score),
                       ("CTR", sc.CTR_score), ("Trust", sc.trust_score),
                       ("Clarity", sc.clarity_score), ("SEO", sc.seo_score),
                       ("Mobile", sc.mobile_score)]:
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 11)
        c.drawString(0.9 * inch, y, f"{val.score:>3}")
        c.setFillColor(IVORY); c.setFont("Helvetica", 11)
        c.drawString(1.45 * inch, y, label)
        y -= 18

    # Copy page
    c.showPage(); bg()
    y = h1("Listing copy", H - 1.1 * inch)
    y = para("TITLE: " + ls.titles[0].title, y, size=11, color=GOLD)
    y -= 6
    for b in ls.description_blocks:
        y = para(b.heading.upper(), y, size=11, color=GOLD, font="Helvetica-Bold")
        y = para(b.body, y) - 8
    y = para("TAGS: " + ", ".join(ls.tags), y - 4, color=GOLD)

    # Buyer psychology page
    c.showPage(); bg()
    y = h1("Buyer decision analysis", H - 1.1 * inch)
    for k, v in output.buyer_decision_engine.scores.model_dump().items():
        y = para(f"{k.replace('_', ' ').replace(' score', '').title()}: {v}", y, size=11)
    y -= 10
    y = para("TOP UNCERTAINTIES", y, size=11, color=GOLD, font="Helvetica-Bold")
    for u in sorted(output.buyer_decision_engine.buyer_uncertainty_map,
                    key=lambda x: -x.severity)[:6]:
        y = para(f"[sev {u.severity}] {u.uncertainty}", y) - 2

    # Image system page
    c.showPage(); bg()
    y = h1("7-image conversion system", H - 1.1 * inch)
    images = (db.query(ListingImage)
              .filter(ListingImage.listing_id == listing.id,
                      ListingImage.superseded.is_(False))
              .order_by(ListingImage.display_order).all())
    slot_by_id = {s.slot_id: s for s in output.image_prompts.slots}
    for img in images:
        s = slot_by_id.get(img.slot_id)
        y = para(f"#{img.display_order} — {s.required_visual_type if s else ''} "
                 f"(pixel score {img.validation_score}/100)", y, size=11, color=GOLD,
                 font="Helvetica-Bold")
        if s:
            y = para(s.objective, y) - 6

    c.save()
    return buf.getvalue()


def asset_zip(db: Session, listing: Listing) -> bytes:
    """Everything a seller needs in one package."""
    output = ListingOutput.model_validate(listing.output_json)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("listing.json", listing_json(listing))
        z.writestr("listing.csv", listing_csv(listing))
        z.writestr("etsy_paste_ready.txt", etsy_paste(listing))
        z.writestr("report.pdf", pdf_report(db, listing))
        images = (db.query(ListingImage)
                  .filter(ListingImage.listing_id == listing.id,
                          ListingImage.superseded.is_(False))
                  .order_by(ListingImage.display_order).all())
        for img in images:
            p = Path(img.image_url)
            if p.exists():
                z.writestr(f"images/{img.display_order:02d}_slot{img.slot_id}.png",
                           p.read_bytes())
        prompts = "\n\n---\n\n".join(
            f"SLOT {s.slot_id}\n{s.prompt.render()}" for s in output.image_prompts.slots)
        z.writestr("image_prompts.txt", prompts)
    return buf.getvalue()
