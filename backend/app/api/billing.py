"""
Stripe Billing Integration

Flow:
1. Frontend calls POST /api/billing/checkout → returns Stripe Checkout URL
2. Customer pays on Stripe's hosted page
3. Stripe sends webhook to POST /api/billing/webhook
4. Webhook handler updates Subscription in DB
"""

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Subscription, Plan, SubscriptionStatus
from app.auth import get_current_user
from app.config import settings

stripe.api_key = settings.stripe_secret_key
router = APIRouter()

# Price IDs — create these in Stripe Dashboard
PLAN_PRICES = {
    Plan.STARTER: "price_starter_id",       # replace with real Stripe Price ID
    Plan.PRO: "price_pro_id",               # ~$149/mo
    Plan.ENTERPRISE: "price_enterprise_id", # ~$499/mo
}


@router.post("/checkout")
async def create_checkout(
    plan: Plan,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    price_id = PLAN_PRICES.get(plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    # Get or create Stripe customer
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = sub_result.scalar_one_or_none()

    if subscription and subscription.stripe_customer_id:
        customer_id = subscription.stripe_customer_id
    else:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        customer_id = customer.id

    checkout = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url="http://localhost:3000/dashboard?checkout=success",
        cancel_url="http://localhost:3000/dashboard?checkout=cancelled",
        metadata={"user_id": str(user.id), "plan": plan.value},
    )

    return {"url": checkout.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle subscription events
    if event["type"] in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        data = event["data"]["object"]
        user_id = data.get("metadata", {}).get("user_id")
        if user_id:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.stripe_subscription_id = data["id"]
                sub.stripe_customer_id = data["customer"]
                sub.status = SubscriptionStatus(data.get("status", "active"))
                await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        data = event["data"]["object"]
        user_id = data.get("metadata", {}).get("user_id")
        if user_id:
            result = await db.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = SubscriptionStatus.CANCELLED
                await db.commit()

    return {"status": "received"}
