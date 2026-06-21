"""Pydantic schemas for request/response validation."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class ProfileResponse(BaseModel):
    id: str
    profile_name: str
    whatsapp_number: Optional[str] = None
    gateway_status: str
    personality: str
    email_accounts: list = []
    enabled_skills: list = []

    class Config:
        from_attributes = True


class UpdatePersonalityRequest(BaseModel):
    personality: str


class AddEmailRequest(BaseModel):
    email_type: str  # gmail, outlook, custom
    email_address: EmailStr
    app_password: str


class UpdateSkillsRequest(BaseModel):
    skills: list[str]


class UserSummary(BaseModel):
    id: str
    email: str
    name: str
    status: str
    plan: str
    subscription_status: str
    profile_name: Optional[str] = None
    gateway_status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
