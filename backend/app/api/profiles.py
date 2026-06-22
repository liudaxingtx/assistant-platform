from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, HermesProfile, Subscription, ProfileStatus, SubscriptionStatus, Plan
from app.auth import get_current_user
from app.schemas import (
    ProfileResponse,
    UpdatePersonalityRequest,
    AddEmailRequest,
    UpdateSkillsRequest,
)
from app.services.hermes_manager import HermesManager
from app.services.gateway_supervisor import GatewaySupervisor

router = APIRouter()


def _auto_restart_gateway(profile_name: str, profile_status_ref=None):
    """After config change, restart the gateway if it was running.
    Returns the new status string."""
    try:
        result = GatewaySupervisor.restart(profile_name)
        new_status = result.get("start", {}).get("status", "offline")
        return new_status
    except Exception:
        return "error"


@router.get("/me")
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet — contact support")
    
    # Get real-time gateway status from supervisor
    actual_status = GatewaySupervisor.status(profile.profile_name)
    if actual_status != profile.gateway_status.value:
        profile.gateway_status = ProfileStatus(actual_status)
        await db.commit()
    
    # Also get subscription info
    sub_result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    
    return {
        "id": str(profile.id),
        "profile_name": profile.profile_name,
        "whatsapp_number": profile.whatsapp_number,
        "gateway_status": actual_status,
        "personality": profile.personality,
        "email_accounts": profile.email_accounts or [],
        "enabled_skills": profile.enabled_skills or [],
        "plan": sub.plan.value if sub else "starter",
    }


@router.put("/me/plan")
async def update_plan(
    req: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = req.get("plan", "starter")
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription")
    sub.plan = Plan(plan)
    await db.commit()
    return {"status": "ok", "plan": plan}


@router.put("/me/personality")
async def update_personality(
    req: UpdatePersonalityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet")
    profile.personality = req.personality
    await db.commit()
    HermesManager.configure_personality(profile.profile_name, req.personality)
    
    # Auto-restart gateway so new persona takes effect
    _auto_restart_gateway(profile.profile_name)
    
    return {"status": "ok"}


@router.post("/me/email")
async def add_email(
    req: AddEmailRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet")
    accounts = list(profile.email_accounts or [])
    accounts.append({
        "type": req.email_type,
        "email": req.email_address,
        "app_password": req.app_password,
    })
    profile.email_accounts = accounts
    await db.commit()
    HermesManager.configure_email(
        profile.profile_name,
        req.email_type,
        {"email": req.email_address, "app_password": req.app_password},
    )
    
    # Auto-restart gateway so new email account works
    _auto_restart_gateway(profile.profile_name)
    
    return {"status": "ok", "accounts": len(accounts)}


@router.put("/me/whatsapp")
async def update_whatsapp(
    req: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet")
    whatsapp_number = req.get("whatsapp_number", "").strip()
    if not whatsapp_number:
        raise HTTPException(status_code=400, detail="Phone number required")
    profile.whatsapp_number = whatsapp_number
    profile.gateway_status = ProfileStatus.PENDING
    await db.commit()
    HermesManager.configure_gateway(profile.profile_name, whatsapp_number)
    
    # Auto-restart gateway with new WhatsApp config
    new_status = _auto_restart_gateway(profile.profile_name)
    profile.gateway_status = ProfileStatus(new_status) if new_status in ("online", "offline", "pending", "error") else ProfileStatus.ONLINE
    await db.commit()
    
    return {"status": "ok", "whatsapp_number": whatsapp_number, "gateway_status": new_status}


@router.delete("/me/email/{index}")
async def remove_email(
    index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet")
    accounts = list(profile.email_accounts or [])
    if index < 0 or index >= len(accounts):
        raise HTTPException(status_code=400, detail="Invalid email index")
    accounts.pop(index)
    profile.email_accounts = accounts
    await db.commit()
    
    # Auto-restart gateway
    _auto_restart_gateway(profile.profile_name)
    
    return {"status": "ok", "accounts": len(accounts)}


@router.put("/me/skills")
async def update_skills(
    req: UpdateSkillsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HermesProfile).where(HermesProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile yet")
    profile.enabled_skills = req.skills
    await db.commit()
    
    # Auto-restart gateway
    _auto_restart_gateway(profile.profile_name)
    
    return {"status": "ok", "skills": req.skills}
