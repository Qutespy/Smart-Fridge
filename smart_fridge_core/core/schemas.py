from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import List, Optional, Dict
from enum import Enum

# ========== Пользователи и семья ==========
class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.MEMBER

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    family_id: Optional[int]
    created_at: datetime
    is_active: bool = True

class Family(BaseModel):
    id: int
    name: str
    admin_id: int
    created_at: datetime

class Device(BaseModel):
    id: int
    serial_number: str
    family_id: int
    is_active: bool = True
    last_seen: Optional[datetime]

# ========== Продукты ==========
class ProductCategory(str, Enum):
    DAIRY = "dairy"
    MEAT = "meat"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"
    BEVERAGE = "beverage"
    OTHER = "other"

class ProductBase(BaseModel):
    name: str
    category: ProductCategory = ProductCategory.OTHER
    default_shelf_life_days: Optional[int]  # срок годности по умолчанию

class ProductCatalog(ProductBase):
    id: int
    barcode: Optional[str]


class ProductCatalogCreate(BaseModel):
    name: str
    category: ProductCategory = ProductCategory.OTHER
    default_shelf_life_days: Optional[int] = None
    photo_url: Optional[str] = None


class ProductCatalogOut(BaseModel):
    id: int
    name: str
    category: str
    default_shelf_life_days: Optional[int] = None
    barcode: Optional[str] = None
    photo_url: Optional[str] = None

    class Config:
        from_attributes = True

class FridgeItem(BaseModel):
    id: int
    family_id: int
    product_id: int
    product_name: str
    quantity: float
    unit: str = "шт"
    expiration_date: date
    added_date: datetime
    added_by_user_id: int
    photo_url: Optional[str]
    notes: Optional[str]

class FridgeItemCreate(BaseModel):
    product_id: int
    quantity: float = 1.0
    expiration_date: date
    photo_url: Optional[str] = None

# ========== Рецепты ==========
class RecipeBase(BaseModel):
    title: str
    instructions: str
    calories: int
    prep_time_minutes: int
    image_url: Optional[str]
    difficulty: str = "medium"  # easy, medium, hard

class RecipeCreate(RecipeBase):
    ingredients: List[str]

class Recipe(RecipeBase):
    id: int
    ingredients: List[str]  # через relation
    created_at: datetime

class RecipeSuggestion(BaseModel):
    recipe: Recipe
    match_percentage: float
    missing_ingredients: List[str]

# ========== Списки покупок ==========
class ShoppingList(BaseModel):
    id: int
    family_id: int
    title: str
    created_at: datetime
    is_active: bool = True

class ShoppingListItem(BaseModel):
    id: int
    list_id: int
    product_name: str
    quantity: float
    unit: str
    is_purchased: bool = False
    notes: Optional[str]

# ========== Уведомления ==========
class NotificationType(str, Enum):
    EXPIRED = "expired"
    EXPIRING_SOON = "expiring_soon"
    LOW_STOCK = "low_stock"
    RECIPE_SUGGESTION = "recipe_suggestion"

class Notification(BaseModel):
    id: int
    user_id: int
    type: NotificationType
    title: str
    message: str
    data: Optional[Dict]
    created_at: datetime
    is_read: bool = False

# ========== AI и мониторинг ==========
class ScanResult(BaseModel):
    product_name: str
    confidence: float
    expiration_date: Optional[date]
    barcode: Optional[str]

class SensorData(BaseModel):
    device_id: int
    temperature: float  # °C
    humidity: float  # %
    timestamp: datetime
# ========== События и статистика холодильника ==========
class InventoryActionType(str, Enum):
    CONSUMED = "consumed"
    WASTED = "wasted"
    ADJUSTED = "adjusted"


class InventoryItemAction(BaseModel):
    action: InventoryActionType
    quantity: float = Field(default=1.0, gt=0)
    reason: Optional[str] = None


class InventoryEventOut(BaseModel):
    id: int
    product_name: str
    quantity: float
    unit: str
    action: str
    reason: Optional[str] = None
    expiration_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True
