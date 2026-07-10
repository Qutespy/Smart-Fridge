"""
Seed script — populates the database with demo data for presentation.

Usage:
    cd SmartFridge-main-2/smart_fridge_core
    python seed.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta, datetime
from core.database import engine, SessionLocal, Base
from models.user import UserModel, FamilyModel
from models.product import ProductCatalogModel, FridgeItemModel
from models.recipe import RecipeModel
from services.auth_service.auth_handler import AuthHandler
import models  # noqa: F401


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(UserModel).first():
        print("Database already seeded. Skipping.")
        db.close()
        return

    family = FamilyModel(name="Demo Family", admin_id=1)
    db.add(family)
    db.flush()

    auth = AuthHandler(db)
    user = UserModel(
        email="demo@smartfridge.com",
        full_name="Demo User",
        hashed_password=auth.get_password_hash("demo123"),
        role="admin",
        family_id=family.id,
    )
    db.add(user)
    db.flush()

    family.admin_id = user.id

    products = [
        ("Молоко", "dairy", 7, "4607025392408", "/static/images/products/milk.jpg"),
        ("Сыр Гауда", "dairy", 30, "4607025392415", "/static/images/products/cheese-gouda.jpg"),
        ("Йогурт", "dairy", 14, "4607025392422", "/static/images/products/yogurt.jpg"),
        ("Куриная грудка", "meat", 3, "4607025392439", "/static/images/products/chicken-breast.jpg"),
        ("Яйца", "other", 21, "4607025392446", "/static/images/products/eggs.jpg"),
        ("Хлеб белый", "other", 5, "4607025392453", "/static/images/products/bread-white.jpg"),
        ("Масло сливочное", "dairy", 60, "4607025392460", "/static/images/products/butter.jpg"),
        ("Помидоры", "vegetable", 7, None, "/static/images/products/tomatoes.jpg"),
        ("Огурцы", "vegetable", 5, None, "/static/images/products/cucumbers.jpg"),
        ("Яблоки", "fruit", 14, None, "/static/images/products/apples.jpg"),
        ("Апельсиновый сок", "beverage", 10, "4607025392477", "/static/images/products/orange-juice.jpg"),
        ("Сметана", "dairy", 14, "4607025392484", "/static/images/products/sour-cream.jpg"),
    ]

    product_models = []
    for name, cat, shelf_life, barcode, photo_url in products:
        p = ProductCatalogModel(
            name=name,
            category=cat,
            default_shelf_life_days=shelf_life,
            barcode=barcode,
            photo_url=photo_url,
        )
        db.add(p)
        db.flush()
        product_models.append(p)

    today = date.today()
    fridge_data = [
        (0, 1.0, today - timedelta(days=2)),   # expired
        (1, 0.5, today + timedelta(days=15)),
        (2, 2.0, today + timedelta(days=1)),    # expiring soon
        (3, 0.3, today + timedelta(days=1)),    # expiring soon + low stock
        (4, 10.0, today + timedelta(days=14)),
        (5, 0.5, today + timedelta(days=3)),
        (6, 1.0, today + timedelta(days=45)),
        (7, 3.0, today + timedelta(days=4)),
        (8, 2.0, today + timedelta(days=3)),
        (9, 5.0, today + timedelta(days=10)),
        (10, 1.0, today + timedelta(days=7)),
        (11, 0.2, today + timedelta(days=5)),   # low stock
    ]

    for idx, qty, exp_date in fridge_data:
        item = FridgeItemModel(
            family_id=family.id,
            product_id=product_models[idx].id,
            product_name=product_models[idx].name,
            quantity=qty,
            expiration_date=exp_date,
            added_by_user_id=user.id,
            photo_url=product_models[idx].photo_url,
        )
        db.add(item)

    recipes = [
        RecipeModel(
            title="Салат Цезарь",
            instructions="1. Нарежьте куриную грудку. 2. Обжарьте. 3. Смешайте с салатом, сухариками и сыром. 4. Полейте соусом.",
            calories=350,
            prep_time_minutes=25,
            difficulty="easy",
            ingredients=["Куриная грудка", "Сыр Гауда", "Хлеб белый", "Яйца"],
        ),
        RecipeModel(
            title="Овощной салат",
            instructions="1. Нарежьте помидоры и огурцы. 2. Посолите. 3. Заправьте маслом или сметаной.",
            calories=120,
            prep_time_minutes=10,
            difficulty="easy",
            ingredients=["Помидоры", "Огурцы", "Масло сливочное"],
        ),
        RecipeModel(
            title="Омлет с сыром",
            instructions="1. Взбейте яйца с молоком. 2. Вылейте на разогретую сковороду. 3. Посыпьте тертым сыром. 4. Накройте крышкой на 3 мин.",
            calories=280,
            prep_time_minutes=15,
            difficulty="easy",
            ingredients=["Яйца", "Молоко", "Сыр Гауда", "Масло сливочное"],
        ),
        RecipeModel(
            title="Фруктовый смузи",
            instructions="1. Нарежьте яблоки. 2. Смешайте с йогуртом и соком в блендере.",
            calories=180,
            prep_time_minutes=5,
            difficulty="easy",
            ingredients=["Яблоки", "Йогурт", "Апельсиновый сок"],
        ),
    ]
    for r in recipes:
        db.add(r)

    db.commit()
    db.close()
    print("Database seeded successfully!")
    print("  Login: demo@smartfridge.com / demo123")


if __name__ == "__main__":
    seed()
