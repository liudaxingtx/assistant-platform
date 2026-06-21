"""
AI Assistant Platform — Complete Database Models

User → Subscription → HermesProfile
One user has one subscription and one Hermes profile.
"""

import uuid
from datetime import datetime
import uuid as _uuid
from sqlalchemy import Column, String, DateTime, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship
import enum

# Use Text for UUIDs — compatible with both SQLite and PostgreSQL
def _new_uuid():
    return str(_uuid.uuid4())

class Base(DeclarativeBase):
    pass


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Plan(str, enum.Enum):
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"


class ProfileStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PENDING = "pending"
    ERROR = "error"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(SAEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subscription = relationship("Subscription", back_populates="user", uselist=False)
    profile = relationship("HermesProfile", back_populates="user", uselist=False)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    plan = Column(SAEnum(Plan), default=Plan.STARTER, nullable=False)
    status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.TRIALING, nullable=False)
    stripe_subscription_id = Column(String(255), nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscription")


class HermesProfile(Base):
    __tablename__ = "hermes_profiles"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    profile_name = Column(String(64), unique=True, nullable=False)  # hermes profile name on disk
    whatsapp_number = Column(String(30), nullable=True)
    gateway_status = Column(SAEnum(ProfileStatus), default=ProfileStatus.PENDING, nullable=False)
    personality = Column(String(2000), default="You are a helpful AI assistant.", nullable=False)
    email_accounts = Column(JSON, default=list, nullable=False)
    enabled_skills = Column(JSON, default=lambda: ["email", "calendar", "web-search"], nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="profile")
