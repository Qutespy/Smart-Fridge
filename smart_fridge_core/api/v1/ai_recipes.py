"""
Endpoint POST /api/v1/ai-recipes/suggest — генерация рецепта через GigaChat
с пометкой ингредиентов available/fridge_item_id по содержимому холодильника.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.product import FridgeItemModel
from services.ai_recipe_service import (
    generate_recipe,
    RecipeServiceUnavailable,
    RecipeFormatError,
)
from api.v1.auth import get_current_user

router = APIRouter()

_FUZZY_THRESHOLD = 0.72  # эмпирически: «куриная грудка» vs «грудка куриная» → ~0.84


class AIRecipeRequest(BaseModel):
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack"]] = None
    cuisine: Optional[str] = None
    restrictions: list[str] = Field(default_factory=list)
    exclude_titles: list[str] = Field(default_factory=list)


class IngredientResponse(BaseModel):
    name: str
    amount: str
    critical: bool
    available: bool
    fridge_item_id: Optional[int] = None
    substitutes: list[str] = Field(default_factory=list)


class AIRecipeResponse(BaseModel):
    title: str
    description: str
    cuisine: str
    meal_type: str
    cook_time_minutes: int
    difficulty: str
    servings: int
    ingredients: list[IngredientResponse]
    steps: list[str]
    notes: Optional[str] = None


def _normalize(text: str) -> str:
    """Лоуэркейс + только буквы/цифры/пробелы. Для нечёткого сопоставления."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> set[str]:
    """Токены длиной ≥ 3 символов — чтобы не цепляться за «и», «г», «мл»."""
    return {w for w in text.split() if len(w) >= 3}


def match_ingredients_to_fridge(
    ai_ingredients: list[dict],
    fridge_items: list[FridgeItemModel],
) -> list[dict]:
    """
    Для каждого ингредиента из ответа ИИ ищет соответствие в холодильнике.

    Сначала пробуем substring-матч в обе стороны. Затем — токен-оверлап
    (важно: ИИ может писать «куриная грудка», а в холодильнике лежит «грудка
    куриная» — порядок слов разный, character-fuzzy здесь даёт плохой ratio).
    Наконец — SequenceMatcher по отсортированным по словам строкам.
    """
    indexed = []
    for it in fridge_items:
        norm = _normalize(it.product_name or "")
        if norm:
            indexed.append((norm, _tokens(norm), it))

    result: list[dict] = []
    for ing in ai_ingredients:
        ing_copy = dict(ing)
        ing_norm = _normalize(ing.get("name", ""))
        ing_toks = _tokens(ing_norm)
        match_id: Optional[int] = None

        if ing_norm and indexed:
            # 1) substring (быстрый путь)
            for fridge_norm, _ftoks, item in indexed:
                if ing_norm in fridge_norm or fridge_norm in ing_norm:
                    match_id = item.id
                    break

            # 2) token overlap: совпадает хотя бы 1 значимое слово, и оно
            # покрывает большую часть ингредиента или продукта
            if match_id is None and ing_toks:
                for _fnorm, ftoks, item in indexed:
                    if not ftoks:
                        continue
                    common = ing_toks & ftoks
                    if not common:
                        continue
                    coverage = max(
                        len(common) / len(ing_toks),
                        len(common) / len(ftoks),
                    )
                    if coverage >= 0.5:
                        match_id = item.id
                        break

            # 3) fallback: fuzzy по отсортированным токенам (снимает порядок слов)
            if match_id is None:
                ing_sorted = " ".join(sorted(ing_norm.split()))
                best_ratio = 0.0
                best_id: Optional[int] = None
                for fridge_norm, _ftoks, item in indexed:
                    f_sorted = " ".join(sorted(fridge_norm.split()))
                    ratio = SequenceMatcher(None, ing_sorted, f_sorted).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_id = item.id
                if best_ratio >= _FUZZY_THRESHOLD:
                    match_id = best_id

        ing_copy["available"] = match_id is not None
        ing_copy["fridge_item_id"] = match_id
        ing_copy.setdefault("substitutes", [])
        result.append(ing_copy)

    return result


@router.post("/suggest", response_model=AIRecipeResponse)
def suggest_recipe(
    payload: AIRecipeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.family_id:
        raise HTTPException(
            status_code=400,
            detail="Пользователь не привязан к семье — холодильник недоступен",
        )

    fridge_items = (
        db.query(FridgeItemModel)
        .filter(
            FridgeItemModel.family_id == current_user.family_id,
            FridgeItemModel.quantity > 0,
        )
        .all()
    )

    if len(fridge_items) < 3:
        raise HTTPException(
            status_code=400,
            detail="В холодильнике слишком мало продуктов для подбора рецепта (нужно минимум 3)",
        )

    items_for_ai = [
        (it.product_name, f"{it.quantity:g} {it.unit or 'шт'}") for it in fridge_items
    ]

    try:
        recipe = generate_recipe(
            fridge_items=items_for_ai,
            meal_type=payload.meal_type,
            cuisine=payload.cuisine,
            restrictions=payload.restrictions,
            exclude_titles=payload.exclude_titles,
        )
    except RecipeServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Сервис ИИ временно недоступен: {e}")
    except RecipeFormatError as e:
        raise HTTPException(status_code=502, detail=f"ИИ вернул некорректный ответ: {e}")

    recipe["ingredients"] = match_ingredients_to_fridge(recipe["ingredients"], fridge_items)
    return AIRecipeResponse(**recipe)
