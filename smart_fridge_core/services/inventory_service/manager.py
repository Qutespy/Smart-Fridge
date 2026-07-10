from typing import List, Dict, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.product import FridgeItemModel, ProductCatalogModel, InventoryEventModel
from core.config import settings


class InventoryManager:
    def __init__(self, db: Session):
        self.db = db

    def add_item(
        self,
        family_id: int,
        product_id: int,
        quantity: float,
        expiration_date: date,
        user_id: int,
        photo_url: Optional[str] = None,
    ):
        product = (
            self.db.query(ProductCatalogModel)
            .filter(ProductCatalogModel.id == product_id)
            .first()
        )

        if not product:
            raise ValueError(f"Product {product_id} not found in catalog")

        fridge_item = FridgeItemModel(
            family_id=family_id,
            product_id=product_id,
            product_name=product.name,
            quantity=quantity,
            expiration_date=expiration_date,
            added_by_user_id=user_id,
            photo_url=photo_url if photo_url else product.photo_url,
        )

        self.db.add(fridge_item)
        self.db.flush()
        self.db.add(InventoryEventModel(
            family_id=family_id,
            item_id=fridge_item.id,
            product_id=product_id,
            product_name=product.name,
            quantity=quantity,
            unit=fridge_item.unit,
            action="added",
            expiration_date=expiration_date,
            user_id=user_id,
        ))
        self.db.commit()
        self.db.refresh(fridge_item)

        return fridge_item

    def update_quantity(self, item_id: int, new_quantity: float) -> bool:
        item = (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.id == item_id)
            .first()
        )
        if not item:
            return False

        old_quantity = item.quantity
        if new_quantity <= 0:
            self.db.delete(item)
        else:
            item.quantity = new_quantity

        self.db.add(InventoryEventModel(
            family_id=item.family_id,
            item_id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=abs(old_quantity - max(new_quantity, 0)),
            unit=item.unit,
            action="adjusted",
            reason="Корректировка количества",
            expiration_date=item.expiration_date,
            user_id=item.added_by_user_id,
        ))
        self.db.commit()
        return True

    def apply_item_action(
        self,
        item_id: int,
        family_id: int,
        user_id: int,
        action: str,
        quantity: float,
        reason: Optional[str] = None,
    ) -> Optional[FridgeItemModel]:
        item = (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.id == item_id, FridgeItemModel.family_id == family_id)
            .first()
        )
        if not item:
            return None

        quantity_to_write_off = min(quantity, item.quantity)
        self.db.add(InventoryEventModel(
            family_id=family_id,
            item_id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=quantity_to_write_off,
            unit=item.unit,
            action=action,
            reason=reason,
            expiration_date=item.expiration_date,
            user_id=user_id,
        ))

        item.quantity = round(item.quantity - quantity_to_write_off, 3)
        if item.quantity <= 0:
            self.db.delete(item)

        self.db.commit()
        return item

    def get_alerts(self, family_id: int, today: date) -> Dict:
        items = (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.family_id == family_id)
            .all()
        )

        expired = []
        expiring_soon = []
        low_stock = []

        for item in items:
            if item.expiration_date < today:
                expired.append({
                    "name": item.product_name,
                    "expiration_date": item.expiration_date,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "item_id": item.id,
                })
            elif item.expiration_date <= today + timedelta(days=settings.EXPIRATION_WARNING_DAYS):
                days_left = (item.expiration_date - today).days
                expiring_soon.append({
                    "name": item.product_name,
                    "days_left": days_left,
                    "expiration_date": item.expiration_date,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "item_id": item.id,
                })

            if item.quantity < settings.LOW_STOCK_THRESHOLD:
                low_stock.append({
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "item_id": item.id,
                })

        return {
            "CRITICAL_EXPIRED": expired,
            "WARNING_SOON": expiring_soon,
            "LOW_STOCK": low_stock,
        }

    def get_statistics(self, family_id: int, today: Optional[date] = None) -> Dict:
        today = today or date.today()
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)

        items = self.get_inventory_by_family(family_id)
        alerts = self.get_alerts(family_id, today)

        month_events = (
            self.db.query(InventoryEventModel)
            .filter(
                InventoryEventModel.family_id == family_id,
                InventoryEventModel.created_at >= datetime.combine(month_start, datetime.min.time()),
                InventoryEventModel.created_at < datetime.combine(next_month, datetime.min.time()),
            )
            .order_by(InventoryEventModel.created_at.desc())
            .all()
        )

        def sum_action(action: str) -> float:
            return round(sum(e.quantity for e in month_events if e.action == action), 2)

        consumed_events = [e for e in month_events if e.action == "consumed"]
        wasted_events = [e for e in month_events if e.action == "wasted"]
        wasted_expired = [e for e in wasted_events if e.expiration_date and e.expiration_date < today]

        use_first = []
        for item in items:
            days_left = (item.expiration_date - today).days
            if days_left <= settings.EXPIRATION_WARNING_DAYS:
                use_first.append({
                    "item_id": item.id,
                    "name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "expiration_date": item.expiration_date,
                    "days_left": days_left,
                })

        return {
            "total": len(items),
            "expired": len(alerts["CRITICAL_EXPIRED"]),
            "expiring": len(alerts["WARNING_SOON"]),
            "low_stock": len(alerts["LOW_STOCK"]),
            "consumed_month": sum_action("consumed"),
            "wasted_month": sum_action("wasted"),
            "wasted_expired_month": round(sum(e.quantity for e in wasted_expired), 2),
            "month_label": month_start.strftime("%m.%Y"),
            "use_first": use_first[:8],
            "recent_events": [
                {
                    "id": e.id,
                    "product_name": e.product_name,
                    "quantity": e.quantity,
                    "unit": e.unit,
                    "action": e.action,
                    "reason": e.reason,
                    "created_at": e.created_at,
                }
                for e in month_events[:10]
            ],
            "alerts": alerts,
        }

    def search_catalog(self, query: str = "", limit: int = 20) -> List[ProductCatalogModel]:
        q = self.db.query(ProductCatalogModel)
        if query:
            q = q.filter(ProductCatalogModel.name.ilike(f"%{query}%"))
        return q.order_by(ProductCatalogModel.name).limit(limit).all()

    def find_catalog_by_name(self, name: str) -> Optional[ProductCatalogModel]:
        return (
            self.db.query(ProductCatalogModel)
            .filter(func.lower(ProductCatalogModel.name) == name.lower())
            .first()
        )

    def create_catalog_entry(
        self,
        name: str,
        category: str = "other",
        default_shelf_life_days: Optional[int] = None,
        photo_url: Optional[str] = None,
    ) -> ProductCatalogModel:
        existing = self.find_catalog_by_name(name)
        if existing:
            return existing
        product = ProductCatalogModel(
            name=name,
            category=category,
            default_shelf_life_days=default_shelf_life_days,
            photo_url=photo_url,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_inventory_by_family(self, family_id: int) -> List[FridgeItemModel]:
        return (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.family_id == family_id)
            .order_by(FridgeItemModel.expiration_date)
            .all()
        )

    def get_shopping_list(self, family_id: int) -> List[Dict]:
        alerts = self.get_alerts(family_id, date.today())
        low_stock = alerts["LOW_STOCK"]

        return [
            {
                "product_name": item["name"],
                "suggested_quantity": 1.0,
                "current_quantity": item["quantity"],
                "unit": item.get("unit", "шт"),
            }
            for item in low_stock
        ]
