from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from core.database import get_db
from models.shopping import ShoppingListModel, ShoppingListItemModel
from services.inventory_service.manager import InventoryManager
from api.v1.auth import get_current_user

router = APIRouter()


class ShoppingListCreate(BaseModel):
    title: str


class ShoppingListItemCreate(BaseModel):
    product_name: str
    quantity: float = 1.0
    unit: str = "шт"
    notes: Optional[str] = None


@router.get("/lists")
def get_lists(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    family_id = current_user.family_id or 0
    lists = (
        db.query(ShoppingListModel)
        .filter(ShoppingListModel.family_id == family_id)
        .all()
    )
    return [
        {
            "id": sl.id,
            "title": sl.title,
            "is_active": sl.is_active,
            "created_at": str(sl.created_at),
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "is_purchased": item.is_purchased,
                }
                for item in sl.items
            ],
        }
        for sl in lists
    ]


@router.post("/lists", status_code=201)
def create_list(
    data: ShoppingListCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    family_id = current_user.family_id or 0
    sl = ShoppingListModel(family_id=family_id, title=data.title)
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return {"id": sl.id, "title": sl.title}


@router.patch("/lists/{list_id}")
def update_list(
    list_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    sl = db.query(ShoppingListModel).filter(ShoppingListModel.id == list_id).first()
    if not sl:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    sl.is_active = is_active
    db.commit()
    return {"status": "updated"}


@router.get("/auto-generate")
def auto_generate(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    manager = InventoryManager(db)
    return manager.get_shopping_list(current_user.family_id or 0)
