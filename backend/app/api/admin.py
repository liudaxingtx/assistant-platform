from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User, HermesProfile, Subscription, Plan, SubscriptionStatus, ProfileStatus, UserStatus
from app.auth import get_current_user, hash_password
from app.schemas import UserSummary
from app.services.hermes_manager import HermesManager
from app.services.gateway_supervisor import GatewaySupervisor

router = APIRouter()


class CreateClientRequest(BaseModel):
    email: EmailStr
    name: str
    whatsapp_number: str = ""
    plan: Plan = Plan.STARTER


def _user_to_summary(user: User, db=None) -> dict:
    sub = getattr(user, 'subscription', None)
    profile = getattr(user, 'profile', None)
    profile_name = profile.profile_name if profile else None
    # Get real-time gateway status from supervisor
    gateway_status = "offline"
    if profile_name:
        gateway_status = GatewaySupervisor.status(profile_name)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "status": user.status.value,
        "plan": sub.plan.value if sub else "none",
        "subscription_status": sub.status.value if sub else "none",
        "profile_name": profile_name,
        "gateway_status": gateway_status,
        "whatsapp_number": profile.whatsapp_number if profile else None,
        "created_at": str(user.created_at) if user.created_at else None,
    }


# ===== LIST / GET / CREATE =====

@router.get("/clients")
async def list_clients(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_user),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    out = []
    for user in users:
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
async def get_client(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    sub_result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    profile_result = await db.execute(select(HermesProfile).where(HermesProfile.user_id == user.id))
    user.subscription = sub_result.scalar_one_or_none()
    user.profile = profile_result.scalar_one_or_none()
    return _user_to_summary(user)


@router.post("/clients/create")
async def create_client(req: CreateClientRequest, db: AsyncSession = Depends(get_db)):
    """Full provisioning: create user + subscription + hermes profile + gateway config.
    Returns temp_password so admin can share with client."""
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    import uuid
    temp_password = uuid.uuid4().hex[:12]
    user = User(
        email=req.email,
        password_hash=hash_password(temp_password),
        name=req.name,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()

    sub = Subscription(
        user_id=user.id,
        plan=req.plan,
        status=SubscriptionStatus.TRIALING,
    )
    db.add(sub)

    profile_name = f"client-{user.id.replace('-','')[:8]}"
    profile = HermesProfile(
        user_id=user.id,
        profile_name=profile_name,
        whatsapp_number=req.whatsapp_number or None,
        gateway_status=ProfileStatus.PENDING,
    )
    db.add(profile)
    await db.commit()

    # Provision on disk
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
        "temp_password": temp_password,
        "status": "created",
    }


# ===== GATEWAY MANAGEMENT =====

@router.post("/clients/{user_id}/gateway/start")
async def start_gateway(user_id: str, db: AsyncSession = Depends(get_db)):
    """Start the Hermes gateway for this client's profile."""
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")

    gateway_result = GatewaySupervisor.start(profile.profile_name)
    
    # Update DB status
    if gateway_result["status"] == "online":
        profile.gateway_status = ProfileStatus.ONLINE
    elif gateway_result["status"] == "error":
        profile.gateway_status = ProfileStatus.ERROR
    await db.commit()

    return gateway_result


@router.post("/clients/{user_id}/gateway/stop")
async def stop_gateway(user_id: str, db: AsyncSession = Depends(get_db)):
    """Stop the Hermes gateway for this client's profile."""
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")

    gateway_result = GatewaySupervisor.stop(profile.profile_name)
    
    profile.gateway_status = ProfileStatus.OFFLINE
    await db.commit()

    return gateway_result


@router.post("/clients/{user_id}/gateway/restart")
async def restart_gateway(user_id: str, db: AsyncSession = Depends(get_db)):
    """Restart the Hermes gateway for this client's profile."""
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")

    gateway_result = GatewaySupervisor.restart(profile.profile_name)
    
    final_status = gateway_result.get("start", {}).get("status", "error")
    profile.gateway_status = ProfileStatus(final_status) if final_status in ("online", "offline", "error") else ProfileStatus.ERROR
    await db.commit()

    return gateway_result


@router.get("/clients/{user_id}/gateway/status")
async def gateway_status(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get real-time gateway status for a client."""
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")

    status = GatewaySupervisor.status(profile.profile_name)
    return {
        "profile_name": profile.profile_name,
        "status": status,
        "pid": GatewaySupervisor._processes.get(profile.profile_name, None) and \
               GatewaySupervisor._processes[profile.profile_name].pid,
    }


@router.get("/clients/{user_id}/gateway/log")
async def gateway_log(user_id: str, tail: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent gateway log output for a client."""
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")

    return {
        "profile_name": profile.profile_name,
        "log": GatewaySupervisor.get_log(profile.profile_name, tail=tail),
    }


@router.get("/gateways")
async def list_gateways():
    """List all running gateways."""
    return {"gateways": GatewaySupervisor.list_all()}


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(User))
    total_count = len(total_result.scalars().all())
    active_result = await db.execute(select(User).where(User.status == UserStatus.ACTIVE))
    active_count = len(active_result.scalars().all())
    gateways = GatewaySupervisor.list_all()
    return {
        "total_clients": total_count,
        "active_clients": active_count,
        "running_gateways": len(gateways),
    }
