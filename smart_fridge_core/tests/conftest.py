import sys
import os
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from core.database import Base
from models.user import UserModel, FamilyModel
from models.product import ProductCatalogModel, FridgeItemModel
from models.recipe import RecipeModel
from models.device import DeviceModel, SensorDataModel
from models.shopping import ShoppingListModel, ShoppingListItemModel
from models.notification import NotificationModel


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_family(db):
    family = FamilyModel(name="Test Family", admin_id=1)
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@pytest.fixture
def test_user(db, test_family):
    from services.auth_service.auth_handler import AuthHandler
    auth = AuthHandler(db)
    user = UserModel(
        email="test@example.com",
        full_name="Test User",
        hashed_password=auth.get_password_hash("password123"),
        role="member",
        family_id=test_family.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_product(db):
    product = ProductCatalogModel(
        name="Milk",
        category="dairy",
        default_shelf_life_days=7,
        barcode="1234567890",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def test_fridge_item(db, test_family, test_product, test_user):
    item = FridgeItemModel(
        family_id=test_family.id,
        product_id=test_product.id,
        product_name=test_product.name,
        quantity=1.0,
        expiration_date=date(2024, 12, 31),
        added_by_user_id=test_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def test_recipe(db):
    recipe = RecipeModel(
        title="Caesar Salad",
        instructions="Mix ingredients and serve.",
        calories=350,
        prep_time_minutes=15,
        difficulty="easy",
        ingredients=["Lettuce", "Chicken", "Croutons"],
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe
