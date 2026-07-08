from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..billing import (PLANS, check_quota, create_checkout_session,
                       handle_webhook_event, stripe_enabled)
from ..database import User, get_db

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
def plans():
    return PLANS


@router.get("/quota")
def quota(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _, q = check_quota(db, user)
    return q


@router.post("/checkout")
def checkout(body: dict, user: User = Depends(get_current_user)):
    plan = body.get("plan")
    if plan not in ("pro", "scale"):
        raise HTTPException(400, "Plan must be 'pro' or 'scale'.")
    if not stripe_enabled():
        raise HTTPException(501, "Billing is not configured yet. Set STRIPE_SECRET_KEY.")
    url = create_checkout_session(
        user, plan,
        success_url=body.get("success_url", "https://app.listingforge.ai/billing/success"),
        cancel_url=body.get("cancel_url", "https://app.listingforge.ai/billing"),
    )
    return {"checkout_url": url}


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    event = await request.json()
    # Production: verify signature with STRIPE_WEBHOOK_SECRET before trusting.
    handle_webhook_event(db, event)
    return {"received": True}
