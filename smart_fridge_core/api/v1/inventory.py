from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Optional

from core.database import get_db
from core.schemas import FridgeItemCreate, ProductCatalogCreate, ProductCatalogOut, InventoryItemAction
from models.product import FridgeItemModel, ProductCatalogModel
from services.inventory_service.manager import InventoryManager
from api.v1.auth import get_current_user

router = APIRouter()


@router.get("/items")
def get_items(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    manager = InventoryManager(db)
    items = manager.get_inventory_by_family(current_user.family_id or 0)
    return [
        {
            "id": item.id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit": item.unit,
            "expiration_date": str(item.expiration_date),
            "photo_url": item.photo_url,
            "notes": item.notes,
        }
        for item in items
    ]


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(
    item_data: FridgeItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    try:
        item = manager.add_item(
            family_id=current_user.family_id or 0,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            expiration_date=item_data.expiration_date,
            user_id=current_user.id,
            photo_url=item_data.photo_url,
        )
        return {
            "id": item.id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "expiration_date": str(item.expiration_date),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/items/{item_id}")
def update_item(
    item_id: int,
    quantity: float,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    success = manager.update_quantity(item_id, quantity)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "updated"}


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    success = manager.update_quantity(item_id, 0)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted"}


@router.post("/items/{item_id}/action")
def apply_item_action(
    item_id: int,
    payload: InventoryItemAction,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    item = manager.apply_item_action(
        item_id=item_id,
        family_id=current_user.family_id or 0,
        user_id=current_user.id,
        action=payload.action.value if hasattr(payload.action, "value") else payload.action,
        quantity=payload.quantity,
        reason=payload.reason,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "recorded"}


@router.get("/statistics")
def get_statistics(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    manager = InventoryManager(db)
    return manager.get_statistics(current_user.family_id or 0, date.today())


@router.get("/catalog", response_model=List[ProductCatalogOut])
def search_catalog(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    return manager.search_catalog(query=search or "")


@router.post(
    "/catalog",
    response_model=ProductCatalogOut,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog(
    payload: ProductCatalogCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    manager = InventoryManager(db)
    category = payload.category.value if hasattr(payload.category, "value") else payload.category
    product = manager.create_catalog_entry(
        name=payload.name,
        category=category,
        default_shelf_life_days=payload.default_shelf_life_days,
        photo_url=payload.photo_url,
    )
    return product


@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    manager = InventoryManager(db)
    alerts = manager.get_alerts(current_user.family_id or 0, date.today())
    return alerts
