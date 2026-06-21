from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User, HermesProfile, Subscription, Plan, SubscriptionStatus, ProfileStatus, UserStatus
from app.auth import get_current_user
from app.schemas import UserSummary
from app.services.hermes_manager import HermesManager

router = APIRouter()


class CreateClientRequest(BaseModel):
    email: EmailStr
    name: str
    whatsapp_number: str
    plan: Plan = Plan.STARTER


def _user_to_summary(user: User) -> UserSummary:
    sub = user.subscription
    profile = user.profile
    return UserSummary(
        id=str(user.id),
        email=user.email,
        name=user.name,
        status=user.status.value,
        plan=sub.plan.value if sub else "none",
        subscription_status=sub.status.value if sub else "none",
        profile_name=profile.profile_name if profile else None,
        gateway_status=profile.gateway_status.value if profile else None,
        created_at=user.created_at,
    )


@router.get("/clients")
async def list_clients(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_user),  # TODO: admin role check
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    out = []
    for user in users:
        # Fetch subscription + profile
        sub_result = await db.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
        profile_result = await db.execute(
            select(HermesProfile).where(HermesProfile.user_id == user.id)
        )
        user.subscription = sub_result.scalar_one_or_none()
        user.profile = profile_result.scalar_one_or_none()
        out.append(_user_to_summary(user))
    return out


@router.get("/clients/{user_id}")
async def get_client(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404)
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    profile_result = await db.execute(select(HermesProfile).where(HermesProfile.user_id == user.id))
    user.subscription = sub_result.scalar_one_or_none()
    user.profile = profile_result.scalar_one_or_none()
    return _user_to_summary(user)


@router.post("/clients/create")
async def create_client(
    req: CreateClientRequest,
    db: AsyncSession = Depends(get_db),
):
    """Full provisioning: create user + subscription + hermes profile + gateway config."""
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 1. Create User
    import uuid
    from app.auth import hash_password
    temp_password = uuid.uuid4().hex[:12]
    user = User(
        email=req.email,
        password_hash=hash_password(temp_password),
        name=req.name,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()

    # 2. Create Subscription
    sub = Subscription(
        user_id=user.id,
        plan=req.plan,
        status=SubscriptionStatus.TRIALING,
    )
    db.add(sub)

    # 3. Create Hermes Profile on disk + DB
    profile_name = f"client-{user.id.hex[:8]}"
    profile = HermesProfile(
        user_id=user.id,
        profile_name=profile_name,
        whatsapp_number=req.whatsapp_number,
        gateway_status=ProfileStatus.PENDING,
    )
    db.add(profile)
    await db.commit()

    # 4. Provision on disk
    try:
        HermesManager.create_profile(profile_name)
        HermesManager.configure_personality(
            profile_name,
            f"You are {req.name}'s personal AI assistant. "
            "You help manage emails, schedule, research, and daily tasks. "
            "You communicate professionally and proactively.",
        )
        if req.whatsapp_number:
            HermesManager.configure_gateway(profile_name, req.whatsapp_number)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile provisioning failed: {e}")

    return {
        "user_id": str(user.id),
        "profile_name": profile_name,
        "temp_password": temp_password,  # send to client via email
        "status": "created",
    }


@router.post("/clients/{user_id}/restart-gateway")
async def restart_gateway(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(HermesProfile).where(HermesProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404)
    # Restart hermes for this profile
    # In production, use systemd or supervisor
    try:
        HermesManager.delete_profile(profile.profile_name)
        HermesManager.create_profile(profile.profile_name)
        profile.gateway_status = ProfileStatus.ONLINE
        await db.commit()
    except Exception as e:
        profile.gateway_status = ProfileStatus.ERROR
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "restarted"}


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(User))
    total_count = len(total.scalars().all())
    active = await db.execute(select(User).where(User.status == UserStatus.ACTIVE))
    active_count = len(active.scalars().all())
    return {
        "total_clients": total_count,
        "active_clients": active_count,
    }
