import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app
import models  # noqa: F401


engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _register_user(email="user@test.com", password="pass123"):
    return client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Test User",
        "password": password,
    })


def _login(email="user@test.com", password="pass123"):
    return client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })


def _auth_header(email="user@test.com", password="pass123"):
    _register_user(email, password)
    resp = _login(email, password)
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Smart Fridge" in resp.json()["message"]


def test_register():
    resp = _register_user()
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "user@test.com"
    assert "id" in data


def test_register_duplicate():
    _register_user()
    resp = _register_user()
    assert resp.status_code == 400


def test_login_success():
    _register_user()
    resp = _login()
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password():
    _register_user()
    resp = _login(password="wrong")
    assert resp.status_code == 401


def test_me():
    headers = _auth_header()
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@test.com"


def test_inventory_requires_auth():
    resp = client.get("/api/v1/inventory/items")
    assert resp.status_code == 403


def test_inventory_get_items():
    headers = _auth_header()
    resp = client.get("/api/v1/inventory/items", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_inventory_add_item():
    headers = _auth_header()

    db = next(override_get_db())
    from models.product import ProductCatalogModel
    product = ProductCatalogModel(name="Milk", category="dairy")
    db.add(product)
    db.commit()
    db.refresh(product)
    db.close()

    resp = client.post("/api/v1/inventory/items", headers=headers, json={
        "product_id": product.id,
        "quantity": 2.0,
        "expiration_date": "2025-12-31",
    })
    assert resp.status_code == 201
    assert resp.json()["product_name"] == "Milk"


def test_catalog_unauthorized():
    resp = client.get("/api/v1/inventory/catalog")
    assert resp.status_code in (401, 403)


def test_catalog_search_empty_returns_list():
    headers = _auth_header()
    resp = client.get("/api/v1/inventory/catalog", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_catalog_create():
    headers = _auth_header()
    payload = {
        "name": "АПИ Кефир",
        "category": "dairy",
        "default_shelf_life_days": 10,
        "photo_url": "/static/images/products/kefir.jpg",
    }
    resp = client.post("/api/v1/inventory/catalog", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "АПИ Кефир"
    assert data["photo_url"] == "/static/images/products/kefir.jpg"
    assert data["default_shelf_life_days"] == 10


def test_catalog_create_idempotent():
    headers = _auth_header()
    payload = {"name": "АПИ Дубликат", "category": "other"}
    r1 = client.post("/api/v1/inventory/catalog", json=payload, headers=headers)
    r2 = client.post("/api/v1/inventory/catalog", json=payload, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_catalog_search_by_name():
    headers = _auth_header()
    client.post(
        "/api/v1/inventory/catalog",
        json={"name": "Поисковый Тест", "category": "other"},
        headers=headers,
    )
    resp = client.get("/api/v1/inventory/catalog?search=Поиск", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(p["name"] == "Поисковый Тест" for p in data)


def test_inventory_add_item_inherits_photo():
    headers = _auth_header()
    create = client.post(
        "/api/v1/inventory/catalog",
        json={
            "name": "Фото Тест",
            "category": "other",
            "photo_url": "/static/images/products/foto.jpg",
        },
        headers=headers,
    )
    product_id = create.json()["id"]

    add = client.post(
        "/api/v1/inventory/items",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1.0,
            "expiration_date": "2099-01-01",
        },
    )
    assert add.status_code == 201

    items = client.get("/api/v1/inventory/items", headers=headers).json()
    new_item = next(i for i in items if i["product_name"] == "Фото Тест")
    assert new_item["photo_url"] == "/static/images/products/foto.jpg"


def test_recipes_list():
    resp = client.get("/api/v1/recipes/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_recipes_suggestions():
    headers = _auth_header()
    resp = client.get("/api/v1/recipes/suggestions", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
