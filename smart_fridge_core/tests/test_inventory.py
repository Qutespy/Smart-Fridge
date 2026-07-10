from datetime import date, timedelta
from services.inventory_service.manager import InventoryManager
from models.product import ProductCatalogModel, FridgeItemModel


def test_inventory_alerts_expired(db, test_family, test_product, test_user):
    manager = InventoryManager(db)
    today = date(2024, 10, 10)

    manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=1.0,
        expiration_date=date(2024, 10, 5),
        user_id=test_user.id,
    )

    alerts = manager.get_alerts(test_family.id, today)
    assert len(alerts["CRITICAL_EXPIRED"]) == 1
    assert alerts["CRITICAL_EXPIRED"][0]["name"] == "Milk"


def test_inventory_alerts_expiring_soon(db, test_family, test_product, test_user):
    manager = InventoryManager(db)
    today = date(2024, 10, 10)

    manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=1.0,
        expiration_date=date(2024, 10, 11),
        user_id=test_user.id,
    )

    alerts = manager.get_alerts(test_family.id, today)
    assert len(alerts["WARNING_SOON"]) == 1
    assert alerts["WARNING_SOON"][0]["days_left"] == 1


def test_inventory_alerts_low_stock(db, test_family, test_product, test_user):
    manager = InventoryManager(db)
    today = date(2024, 10, 10)

    manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=0.3,
        expiration_date=date(2024, 12, 31),
        user_id=test_user.id,
    )

    alerts = manager.get_alerts(test_family.id, today)
    assert len(alerts["LOW_STOCK"]) == 1
    assert alerts["LOW_STOCK"][0]["quantity"] == 0.3


def test_add_item(db, test_family, test_product, test_user):
    manager = InventoryManager(db)
    item = manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=2.0,
        expiration_date=date(2024, 12, 31),
        user_id=test_user.id,
    )
    assert item.product_name == "Milk"
    assert item.quantity == 2.0


def test_add_item_invalid_product(db, test_family, test_user):
    import pytest
    manager = InventoryManager(db)
    with pytest.raises(ValueError, match="not found"):
        manager.add_item(
            family_id=test_family.id,
            product_id=9999,
            quantity=1.0,
            expiration_date=date(2024, 12, 31),
            user_id=test_user.id,
        )


def test_update_quantity(db, test_fridge_item):
    manager = InventoryManager(db)
    assert manager.update_quantity(test_fridge_item.id, 5.0)
    db.refresh(test_fridge_item)
    assert test_fridge_item.quantity == 5.0


def test_update_quantity_delete(db, test_fridge_item):
    manager = InventoryManager(db)
    item_id = test_fridge_item.id
    assert manager.update_quantity(item_id, 0)
    assert db.query(FridgeItemModel).filter(FridgeItemModel.id == item_id).first() is None


def test_search_catalog_empty_returns_all(db, test_product):
    manager = InventoryManager(db)
    results = manager.search_catalog()
    assert any(p.id == test_product.id for p in results)


def test_search_catalog_by_name(db, test_product):
    manager = InventoryManager(db)
    results = manager.search_catalog(query=test_product.name[:3])
    assert any(p.id == test_product.id for p in results)


def test_search_catalog_no_match(db, test_product):
    manager = InventoryManager(db)
    results = manager.search_catalog(query="ZZZNoSuchThing")
    assert results == []


def test_create_catalog_entry(db):
    manager = InventoryManager(db)
    product = manager.create_catalog_entry(
        name="Тестовый Кефир",
        category="dairy",
        default_shelf_life_days=10,
        photo_url="/static/images/products/kefir.jpg",
    )
    assert product.id is not None
    assert product.name == "Тестовый Кефир"
    assert product.photo_url == "/static/images/products/kefir.jpg"


def test_create_catalog_entry_idempotent(db):
    manager = InventoryManager(db)
    p1 = manager.create_catalog_entry(name="ДубликатТест", category="other")
    p2 = manager.create_catalog_entry(name="ДубликатТест", category="other")
    assert p1.id == p2.id


def test_add_item_inherits_photo_from_catalog(db, test_family, test_product, test_user):
    test_product.photo_url = "/static/images/products/milk.jpg"
    db.commit()

    manager = InventoryManager(db)
    item = manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=1.0,
        expiration_date=date(2099, 1, 1),
        user_id=test_user.id,
    )
    assert item.photo_url == "/static/images/products/milk.jpg"


def test_add_item_explicit_photo_overrides_catalog(db, test_family, test_product, test_user):
    test_product.photo_url = "/static/images/products/milk.jpg"
    db.commit()

    manager = InventoryManager(db)
    item = manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=1.0,
        expiration_date=date(2099, 1, 1),
        user_id=test_user.id,
        photo_url="/static/images/products/custom.jpg",
    )
    assert item.photo_url == "/static/images/products/custom.jpg"


def test_get_shopping_list(db, test_family, test_product, test_user):
    manager = InventoryManager(db)
    manager.add_item(
        family_id=test_family.id,
        product_id=test_product.id,
        quantity=0.2,
        expiration_date=date(2099, 12, 31),
        user_id=test_user.id,
    )
    shopping = manager.get_shopping_list(test_family.id)
    assert len(shopping) == 1
    assert shopping[0]["product_name"] == "Milk"
