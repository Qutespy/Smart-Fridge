from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class FamilyModel(Base):
    __tablename__ = "families"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    admin_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("UserModel", back_populates="family")
    devices = relationship("DeviceModel", back_populates="family")
    fridge_items = relationship("FridgeItemModel", back_populates="family")
    shopping_lists = relationship("ShoppingListModel", back_populates="family")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="member")
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    family = relationship("FamilyModel", back_populates="members")
    notifications = relationship("NotificationModel", back_populates="user")
