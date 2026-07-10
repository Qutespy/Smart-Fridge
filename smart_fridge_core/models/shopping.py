from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class ShoppingListModel(Base):
    __tablename__ = "shopping_lists"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    family = relationship("FamilyModel", back_populates="shopping_lists")
    items = relationship("ShoppingListItemModel", back_populates="shopping_list")


class ShoppingListItemModel(Base):
    __tablename__ = "shopping_list_items"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="шт")
    is_purchased = Column(Boolean, default=False)
    notes = Column(String(500), nullable=True)

    shopping_list = relationship("ShoppingListModel", back_populates="items")
