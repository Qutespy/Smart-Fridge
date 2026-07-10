from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class ProductCatalogModel(Base):
    __tablename__ = "product_catalog"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50), default="other")
    default_shelf_life_days = Column(Integer, nullable=True)
    barcode = Column(String(100), nullable=True, index=True)
    photo_url = Column(String(500), nullable=True)

    fridge_items = relationship("FridgeItemModel", back_populates="product")


class FridgeItemModel(Base):
    __tablename__ = "fridge_items"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_catalog.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="шт")
    expiration_date = Column(Date, nullable=False)
    added_date = Column(DateTime, default=datetime.utcnow)
    added_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    photo_url = Column(String(500), nullable=True)
    notes = Column(String(500), nullable=True)

    family = relationship("FamilyModel", back_populates="fridge_items")
    product = relationship("ProductCatalogModel", back_populates="fridge_items")


class InventoryEventModel(Base):
    """История действий с продуктами: съели, выбросили, добавили, скорректировали.

    События позволяют строить честную статистику: продукт больше не исчезает
    бесследно при списании, а сохраняет причину и количество.
    """

    __tablename__ = "inventory_events"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    item_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("product_catalog.id"), nullable=True)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(50), default="шт")
    action = Column(String(32), nullable=False, index=True)  # consumed | wasted | added | adjusted
    reason = Column(String(255), nullable=True)
    expiration_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
