from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User, HermesProfile, Subscription, UserStatus, ProfileStatus, SubscriptionStatus, Plan
from app.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    user: dict


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.flush()

    # Auto-create profile for new users
    import uuid
    profile_name = f"client-{user.id.replace('-','')[:8]}"
    profile = HermesProfile(
        user_id=user.id,
        profile_name=profile_name,
        gateway_status=ProfileStatus.PENDING,
    )
    sub = Subscription(
        user_id=user.id,
        plan=Plan.STARTER,
        status=SubscriptionStatus.TRIALING,
    )
    db.add(profile)
    db.add(sub)
    await db.commit()
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user={"id": str(user.id), "email": user.email, "name": user.name},
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user={"id": str(user.id), "email": user.email, "name": user.name},
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "status": user.status.value,
    }


class UpdateProfileRequest(BaseModel):
    name: str


@router.put("/me")
async def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.name = req.name
    await db.commit()
    return {"id": str(user.id), "email": user.email, "name": user.name}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/me/password")
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user.password_hash = hash_password(req.new_password)
    await db.commit()
    return {"status": "ok"}
