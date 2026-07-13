"""Database layer. SQLite in dev, Postgres in production (set DATABASE_URL)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text, create_engine)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from .config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    plan = Column(String, default="free")  # free | pro | scale
    stripe_customer_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)
    is_active = Column(Boolean, default=True)

    listings = relationship("Listing", back_populates="owner", cascade="all, delete-orphan")
    usage = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")


class Listing(Base):
    __tablename__ = "listings"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    input_description = Column(Text, default="")
    input_price = Column(Float, nullable=True)
    input_notes = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft | generating | complete | failed
    category = Column(String, nullable=True)
    output_json = Column(JSON, nullable=True)   # full ListingOutput
    progress_json = Column(JSON, nullable=True)  # {step, index, total} while generating
    context_json = Column(JSON, nullable=True)   # ListingContext snapshot (Phase 5)
    batch_id = Column(String, nullable=True, index=True)  # bulk-generation batch
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    owner = relationship("User", back_populates="listings")
    uploads = relationship("Upload", back_populates="listing", cascade="all, delete-orphan")


class Upload(Base):
    __tablename__ = "uploads"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    listing_id = Column(String, ForeignKey("listings.id"), index=True, nullable=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    path = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)

    listing = relationship("Listing", back_populates="uploads")


class ListingImage(Base):
    """Final generated image per slot, with version history via superseded flag."""
    __tablename__ = "listing_images"
    id = Column(String, primary_key=True, default=_uuid)
    listing_id = Column(String, ForeignKey("listings.id"), index=True, nullable=False)
    slot_id = Column(Integer, nullable=False)
    display_order = Column(Integer, nullable=True)  # Etsy upload position 1-7
    image_url = Column(String, nullable=False)      # storage path or CDN url
    prompt_used = Column(Text, nullable=False)
    style_profile = Column(String, nullable=False)
    score_json = Column(JSON, nullable=True)        # validation scores
    validation_score = Column(Float, default=0.0)   # composite 0-100
    regeneration_count = Column(Integer, default=0)
    superseded = Column(Boolean, default=False)     # older versions kept, flagged
    provider = Column(String, default="local_studio")
    created_at = Column(DateTime, default=_now)


class ImageGenerationLog(Base):
    """Every attempt, pass or fail — prompt history + failure reasons."""
    __tablename__ = "image_generation_logs"
    id = Column(String, primary_key=True, default=_uuid)
    listing_id = Column(String, ForeignKey("listings.id"), index=True, nullable=False)
    slot_id = Column(Integer, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    passed = Column(Boolean, default=False)
    failure_reason = Column(Text, nullable=True)
    score_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=_now)


class EtsyConnection(Base):
    """OAuth tokens for a user's Etsy shop."""
    __tablename__ = "etsy_connections"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    shop_id = Column(String, nullable=True)
    shop_name = Column(String, nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    oauth_state = Column(String, nullable=True)       # CSRF state during handshake
    code_verifier = Column(String, nullable=True)     # PKCE verifier during handshake
    created_at = Column(DateTime, default=_now)


class PublishedListing(Base):
    __tablename__ = "published_listings"
    id = Column(String, primary_key=True, default=_uuid)
    listing_id = Column(String, ForeignKey("listings.id"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    etsy_listing_id = Column(String, nullable=False)
    etsy_url = Column(String, nullable=True)
    state = Column(String, default="draft")  # draft | active
    payload_json = Column(JSON, nullable=True)
    published_at = Column(DateTime, default=_now)


class ListingMetric(Base):
    """Post-publish analytics snapshots — the self-improving loop's raw data."""
    __tablename__ = "listing_metrics"
    id = Column(String, primary_key=True, default=_uuid)
    published_listing_id = Column(String, ForeignKey("published_listings.id"), index=True, nullable=False)
    views = Column(Integer, default=0)
    favorites = Column(Integer, default=0)
    ctr_proxy = Column(Float, nullable=True)          # favorites/views when available
    raw_json = Column(JSON, nullable=True)
    captured_at = Column(DateTime, default=_now)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    kind = Column(String, nullable=False)   # generation | publish | optimization | credits | batch
    title = Column(String, nullable=False)
    body = Column(Text, default="")
    link = Column(String, nullable=True)    # in-app path, e.g. listing id
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)


class BrandProfile(Base):
    """One brand system per user, injected into every generation."""
    __tablename__ = "brand_profiles"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    brand_name = Column(String, default="")
    voice = Column(Text, default="")                # e.g. "editorial, precise, warm"
    photography_style = Column(Text, default="")    # e.g. "macro luxury, soft shadows"
    packaging_guidelines = Column(Text, default="")
    messaging_pillars = Column(JSON, default=list)  # ["heirloom quality", ...]
    palette = Column(Text, default="")              # e.g. "obsidian, ivory, antique gold"
    apply_to_generations = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class ListingEvent(Base):
    """Learning engine event stream: everything that happens to a listing."""
    __tablename__ = "listing_events"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    listing_id = Column(String, ForeignKey("listings.id"), index=True, nullable=True)
    kind = Column(String, nullable=False)  # generated|edited|assist|regen|restore|reorder|published|export|metrics
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)


class BrandMemoryItem(Base):
    """Learned brand preferences with evidence counts (Phase 5)."""
    __tablename__ = "brand_memory"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    key = Column(String, nullable=False)      # e.g. preferred_style:macro_detail
    value = Column(JSON, default=dict)
    evidence_count = Column(Integer, default=1)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    name = Column(String, primary_key=True)
    enabled = Column(Boolean, default=True)
    rollout_pct = Column(Integer, default=100)   # staged rollout 0-100
    note = Column(Text, default="")
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Job(Base):
    """DB-backed background job queue: survives restarts (Phase 5)."""
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, index=True, nullable=False)
    kind = Column(String, nullable=False)        # generate_listing | bulk_item
    payload = Column(JSON, default=dict)
    status = Column(String, default="queued", index=True)  # queued|running|done|failed
    attempts = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Product(Base):
    """A digital product the seller describes on the Generate page.
    Minimal-question intake: images (+ optional product file) carry most of
    the information; name may be AI-inferred after generation."""
    __tablename__ = "products"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)      # "Group / Subcategory"
    style = Column(String, nullable=True)
    target_audience = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    brand_name = Column(String, nullable=True)          # optional brand style
    color_preferences = Column(String, nullable=True)
    file_link = Column(String, nullable=True)           # e.g. Canva share link
    files = Column(JSON, default=list)  # [{upload_id,name,type,path,kind:image|asset}]
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


class GrowthListing(Base):
    """A generated growth listing: the complete ListingResult JSON + score."""
    __tablename__ = "growth_listings"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    product_id = Column(String, ForeignKey("products.id"), index=True, nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, default="generated")
    score = Column(Integer, default=0)
    saved = Column(Boolean, default=False)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Profile(Base):
    """Account settings: display name + shop/brand name."""
    __tablename__ = "profiles"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    display_name = Column(String, nullable=True)
    brand_name = Column(String, nullable=True)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), index=True, nullable=False)
    kind = Column(String, default="listing_generation")
    listing_id = Column(String, nullable=True)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="usage")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
