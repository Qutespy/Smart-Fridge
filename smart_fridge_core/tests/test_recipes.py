from services.recipe_service.engine import RecipeEngine
from models.product import FridgeItemModel, ProductCatalogModel
from models.recipe import RecipeModel
from datetime import date


def _add_recipe(db, title, ingredients):
    r = RecipeModel(
        title=title,
        instructions="Test instructions",
        calories=200,
        prep_time_minutes=10,
        difficulty="easy",
        ingredients=ingredients,
    )
    db.add(r)
    db.commit()
    return r


def _add_inventory(db, family_id, product_names, user_id=1):
    for i, name in enumerate(product_names):
        p = ProductCatalogModel(name=name, category="other")
        db.add(p)
        db.flush()
        item = FridgeItemModel(
            family_id=family_id,
            product_id=p.id,
            product_name=name,
            quantity=1.0,
            expiration_date=date(2099, 12, 31),
            added_by_user_id=user_id,
        )
        db.add(item)
    db.commit()


def test_matching_2_of_3(db, test_family, test_user):
    _add_recipe(db, "Salad", ["Tomato", "Cucumber", "Oil"])
    _add_inventory(db, test_family.id, ["Tomato", "Cucumber"], test_user.id)

    engine = RecipeEngine(db)
    results = engine.suggest_by_inventory(test_family.id)
    assert len(results) == 1
    assert results[0].match_percentage >= 60


def test_matching_3_of_3(db, test_family, test_user):
    _add_recipe(db, "Full Salad", ["Tomato", "Cucumber", "Oil"])
    _add_inventory(db, test_family.id, ["Tomato", "Cucumber", "Oil"], test_user.id)

    engine = RecipeEngine(db)
    results = engine.suggest_by_inventory(test_family.id)
    assert len(results) == 1
    assert results[0].match_percentage == 100


def test_matching_0_of_3(db, test_family, test_user):
    _add_recipe(db, "Pasta", ["Pasta", "Sauce", "Cheese"])
    _add_inventory(db, test_family.id, ["Tomato", "Cucumber"], test_user.id)

    engine = RecipeEngine(db)
    results = engine.suggest_by_inventory(test_family.id)
    assert len(results) == 0


def test_empty_inventory(db, test_family):
    _add_recipe(db, "Soup", ["Potato", "Carrot", "Onion"])

    engine = RecipeEngine(db)
    results = engine.suggest_by_inventory(test_family.id)
    assert len(results) == 0


def test_missing_ingredients(db, test_family, test_user):
    _add_recipe(db, "Sandwich", ["Bread", "Cheese", "Ham"])
    _add_inventory(db, test_family.id, ["Bread", "Cheese"], test_user.id)

    engine = RecipeEngine(db)
    results = engine.suggest_by_inventory(test_family.id)
    assert len(results) == 1
    assert "ham" in results[0].missing_ingredients
