"""
Тесты для /api/v1/ai-recipes/suggest и для match_ingredients_to_fridge.
GigaChat не дёргается — patch на api.v1.ai_recipes.generate_recipe.
"""
import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app
import models  # noqa: F401

from api.v1.ai_recipes import match_ingredients_to_fridge
from services.ai_recipe_service import (
    RecipeServiceUnavailable,
    RecipeFormatError,
    parse_response,
    validate_recipe,
    build_prompt,
)


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def setup_db():
    """
    Создаём таблицы в собственной in-memory БД и временно перенаправляем
    зависимость get_db на наш TestSession. По окончании теста — восстанавливаем
    исходный override (если был от другого тестового модуля), иначе сносим.
    """
    Base.metadata.create_all(bind=engine)
    prev_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield
    finally:
        if prev_override is not None:
            app.dependency_overrides[get_db] = prev_override
        else:
            app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


# --- helpers --- #

FAKE_RECIPE = {
    "title": "Тестовый рецепт",
    "description": "Описание",
    "cuisine": "русская",
    "meal_type": "dinner",
    "cook_time_minutes": 30,
    "difficulty": "easy",
    "servings": 2,
    "ingredients": [
        {"name": "молоко", "amount": "200 мл", "critical": True, "substitutes": []},
        {"name": "хлеб", "amount": "100 г", "critical": False, "substitutes": ["батон"]},
    ],
    "steps": ["шаг 1", "шаг 2"],
    "notes": None,
}


def _register_user(email="recipe_user@test.com", password="pass123"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Recipe Tester", "password": password},
    )


def _login(email="recipe_user@test.com", password="pass123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _auth_header(email="recipe_user@test.com", password="pass123"):
    _register_user(email, password)
    return {"Authorization": f"Bearer {_login(email, password).json()['access_token']}"}


def _seed_family_and_items(user_email="recipe_user@test.com", n_items=3):
    """
    Заводит семью, привязывает к ней пользователя, кладёт n_items продуктов в
    холодильник. Возвращает family_id и список (product_id, name).
    """
    db = TestSession()
    try:
        from models.user import UserModel, FamilyModel
        from models.product import ProductCatalogModel, FridgeItemModel

        user = db.query(UserModel).filter(UserModel.email == user_email).first()
        family = FamilyModel(name="Test Family", admin_id=user.id)
        db.add(family)
        db.commit()
        db.refresh(family)

        user.family_id = family.id
        db.commit()

        names = ["Молоко", "Хлеб", "Сыр Гауда", "Куриная грудка"][:n_items]
        out = []
        for nm in names:
            p = ProductCatalogModel(name=nm, category="other")
            db.add(p)
            db.commit()
            db.refresh(p)
            it = FridgeItemModel(
                family_id=family.id,
                product_id=p.id,
                product_name=nm,
                quantity=1.0,
                unit="шт",
                expiration_date=date(2099, 1, 1),
                added_by_user_id=user.id,
            )
            db.add(it)
            db.commit()
            db.refresh(it)
            out.append((p.id, nm))
        return family.id, out
    finally:
        db.close()


# --- API endpoint tests --- #


def test_suggest_unauthorized():
    resp = client.post("/api/v1/ai-recipes/suggest", json={})
    assert resp.status_code == 403  # HTTPBearer отдаёт 403, как и в test_api.py


def test_suggest_too_few_items():
    headers = _auth_header()
    _seed_family_and_items(n_items=2)

    with patch("api.v1.ai_recipes.generate_recipe") as mock_gen:
        resp = client.post("/api/v1/ai-recipes/suggest", json={}, headers=headers)
    assert resp.status_code == 400
    assert "минимум 3" in resp.json()["detail"]
    mock_gen.assert_not_called()


def test_suggest_no_family():
    headers = _auth_header()  # пользователь зарегистрирован, но без семьи
    resp = client.post("/api/v1/ai-recipes/suggest", json={}, headers=headers)
    assert resp.status_code == 400
    assert "семь" in resp.json()["detail"].lower()


def test_suggest_happy_path():
    headers = _auth_header()
    _seed_family_and_items(n_items=4)

    with patch("api.v1.ai_recipes.generate_recipe", return_value=dict(FAKE_RECIPE,
        ingredients=[
            {"name": "молоко", "amount": "200 мл", "critical": True, "substitutes": []},
            {"name": "оливковое масло", "amount": "1 ст. ложка", "critical": False, "substitutes": ["подсолнечное"]},
        ])) as mock_gen:
        resp = client.post(
            "/api/v1/ai-recipes/suggest",
            json={"meal_type": "dinner", "cuisine": "русская", "restrictions": ["без глютена"]},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Тестовый рецепт"
    assert body["meal_type"] == "dinner"
    assert body["servings"] == 2

    # молоко есть в холодильнике (нечёткое совпадение с "Молоко")
    milk = next(i for i in body["ingredients"] if i["name"] == "молоко")
    assert milk["available"] is True
    assert milk["fridge_item_id"] is not None

    # оливкового масла нет → available=False, fridge_item_id=null
    oil = next(i for i in body["ingredients"] if i["name"] == "оливковое масло")
    assert oil["available"] is False
    assert oil["fridge_item_id"] is None
    assert oil["substitutes"] == ["подсолнечное"]

    # generate_recipe был вызван с подготовленным списком (name, qty)
    args, kwargs = mock_gen.call_args
    items_arg = kwargs.get("fridge_items") or args[0]
    assert all(isinstance(t, tuple) and len(t) == 2 for t in items_arg)
    assert kwargs.get("meal_type") == "dinner"
    assert kwargs.get("cuisine") == "русская"
    assert kwargs.get("restrictions") == ["без глютена"]


def test_suggest_service_unavailable():
    headers = _auth_header()
    _seed_family_and_items(n_items=3)

    with patch(
        "api.v1.ai_recipes.generate_recipe",
        side_effect=RecipeServiceUnavailable("ключ не настроен"),
    ):
        resp = client.post("/api/v1/ai-recipes/suggest", json={}, headers=headers)
    assert resp.status_code == 503
    assert "недоступен" in resp.json()["detail"]


def test_suggest_format_error():
    headers = _auth_header()
    _seed_family_and_items(n_items=3)

    with patch(
        "api.v1.ai_recipes.generate_recipe",
        side_effect=RecipeFormatError("битый JSON"),
    ):
        resp = client.post("/api/v1/ai-recipes/suggest", json={}, headers=headers)
    assert resp.status_code == 502
    assert "некорректный" in resp.json()["detail"]


# --- match_ingredients_to_fridge unit tests --- #


def _make_fridge_stub(names: list[str]):
    """Лёгкий стаб FridgeItemModel — нам нужны только id и product_name."""
    class Stub:
        def __init__(self, _id, name):
            self.id = _id
            self.product_name = name

    return [Stub(i + 1, n) for i, n in enumerate(names)]


def test_match_exact_case_insensitive():
    items = _make_fridge_stub(["Молоко", "Хлеб"])
    out = match_ingredients_to_fridge(
        [{"name": "молоко", "amount": "200 мл", "critical": True, "substitutes": []}],
        items,
    )
    assert out[0]["available"] is True
    assert out[0]["fridge_item_id"] == 1


def test_match_partial_substring():
    items = _make_fridge_stub(["Куриная грудка свежая"])
    out = match_ingredients_to_fridge(
        [{"name": "куриная грудка", "amount": "300 г", "critical": True, "substitutes": []}],
        items,
    )
    assert out[0]["available"] is True
    assert out[0]["fridge_item_id"] == 1


def test_match_word_order_fuzzy():
    items = _make_fridge_stub(["грудка куриная"])
    out = match_ingredients_to_fridge(
        [{"name": "куриная грудка", "amount": "300 г", "critical": True, "substitutes": []}],
        items,
    )
    assert out[0]["available"] is True
    assert out[0]["fridge_item_id"] == 1


def test_match_not_found():
    items = _make_fridge_stub(["Молоко"])
    out = match_ingredients_to_fridge(
        [{"name": "ананас", "amount": "1 шт", "critical": False, "substitutes": []}],
        items,
    )
    assert out[0]["available"] is False
    assert out[0]["fridge_item_id"] is None


# --- pure-function tests for the gigachat_client helpers --- #


def test_parse_response_clean_json():
    raw = '{"a": 1, "b": "x"}'
    assert parse_response(raw) == {"a": 1, "b": "x"}


def test_parse_response_markdown_wrapped():
    raw = "```json\n{\"a\": 1}\n```"
    assert parse_response(raw) == {"a": 1}


def test_parse_response_with_surrounding_text():
    raw = 'Вот ваш рецепт:\n{"a": 1, "b": [1,2]}\nГотово.'
    assert parse_response(raw) == {"a": 1, "b": [1, 2]}


def test_parse_response_empty_raises():
    with pytest.raises(RecipeFormatError):
        parse_response("")


def test_validate_recipe_ok():
    validate_recipe(FAKE_RECIPE)  # не должно бросать


def test_validate_recipe_missing_field():
    bad = dict(FAKE_RECIPE)
    bad.pop("title")
    with pytest.raises(RecipeFormatError):
        validate_recipe(bad)


def test_validate_recipe_bad_meal_type():
    bad = dict(FAKE_RECIPE, meal_type="midnight")
    with pytest.raises(RecipeFormatError):
        validate_recipe(bad)


def test_validate_recipe_bad_difficulty():
    bad = dict(FAKE_RECIPE, difficulty="extreme")
    with pytest.raises(RecipeFormatError):
        validate_recipe(bad)


def test_build_prompt_includes_items_and_filters():
    sys_p, user_p = build_prompt(
        [("Молоко", "1 шт"), ("Сыр", "200 г")],
        meal_type="dinner",
        cuisine="русская",
        restrictions=["без глютена"],
    )
    assert "JSON" in sys_p
    assert "Молоко" in user_p
    assert "Сыр" in user_p
    assert "ужин" in user_p
    assert "русская" in user_p
    assert "без глютена" in user_p
