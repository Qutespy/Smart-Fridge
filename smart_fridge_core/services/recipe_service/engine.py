from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.product import FridgeItemModel
from models.recipe import RecipeModel
from services.recipe_service.deepseek_client import DeepSeekClient


class RecipeEngine:
    def __init__(self, db: Session, llm_client: Optional[DeepSeekClient] = None):
        self.db = db
        self.llm_client = llm_client or DeepSeekClient()

    def suggest_by_inventory(self, family_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        inventory_items = (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.family_id == family_id)
            .all()
        )

        available_products = {
            item.product_name.lower(): item.quantity for item in inventory_items
        }

        recipes = self.db.query(RecipeModel).all()
        suggestions: List[Dict[str, Any]] = []

        for recipe in recipes:
            ingredients = recipe.ingredients or []
            recipe_ingredients_lower = [i.lower() for i in ingredients]
            matched = []
            missing = []

            for ingredient in recipe_ingredients_lower:
                found = any(
                    product in ingredient or ingredient in product
                    for product in available_products.keys()
                )
                if found:
                    matched.append(ingredient)
                else:
                    missing.append(ingredient)

            total = len(recipe_ingredients_lower)
            match_rate = len(matched) / total if total else 0

            if match_rate >= 0.4:
                suggestions.append(
                    {
                        "recipe": recipe,
                        "match_percentage": round(match_rate * 100, 1),
                        "missing_ingredients": missing[:5],
                    }
                )

        suggestions.sort(key=lambda x: x["match_percentage"], reverse=True)
        return suggestions[:limit]

    def build_inventory_snapshot(self, family_id: int) -> List[Dict[str, Any]]:
        today = date.today()
        items = (
            self.db.query(FridgeItemModel)
            .filter(FridgeItemModel.family_id == family_id)
            .order_by(FridgeItemModel.expiration_date)
            .all()
        )

        result = []
        for item in items:
            days_left = (item.expiration_date - today).days
            result.append(
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "expiration_date": item.expiration_date.isoformat(),
                    "days_left": days_left,
                    "is_urgent": days_left <= 2,
                }
            )
        return result

    def _build_system_prompt(self) -> str:
        return (
            "Ты — AI-ассистент Smart Fridge. "
            "Отвечай только валидным JSON без markdown. "
            "Все поля use_first, missing_ingredients, substitutions, steps "
            "обязательно должны быть массивами строк, даже если элемент один. "
            "Никогда не возвращай строку вместо массива. "
            "JSON должен иметь такую структуру: "
            "{"
            "\"summary\": string,"
            "\"best_choice\": string,"
            "\"general_advice\": string,"
            "\"recipes\": ["
            "{"
            "\"title\": string,"
            "\"why_it_fits\": string,"
            "\"use_first\": [string],"
            "\"missing_ingredients\": [string],"
            "\"substitutions\": [string],"
            "\"steps\": [string],"
            "\"prep_time_minutes\": int,"
            "\"difficulty\": string,"
            "\"calories_estimate\": int"
            "}"
            "]"
            "}"
        )

    def _build_user_prompt(
        self,
        inventory: List[Dict[str, Any]],
        db_recipe_candidates: List[Dict[str, Any]],
        goal: str,
        restrictions: str,
        max_recipes: int,
    ) -> str:
        inventory_lines = []
        for item in inventory:
            urgency = "СРОЧНО ИСПОЛЬЗОВАТЬ" if item["is_urgent"] else "обычно"
            inventory_lines.append(
                f"- {item['product_name']}: {item['quantity']} {item['unit']}, "
                f"срок до {item['expiration_date']}, осталось дней: {item['days_left']}, статус: {urgency}"
            )

        recipe_lines = []
        for candidate in db_recipe_candidates:
            recipe = candidate["recipe"]
            recipe_lines.append(
                f"- {recipe.title} | совпадение: {candidate['match_percentage']}% | "
                f"ингредиенты: {', '.join(recipe.ingredients or [])} | "
                f"не хватает: {', '.join(candidate['missing_ingredients']) if candidate['missing_ingredients'] else 'ничего'}"
            )

        return (
            f"Цель пользователя: {goal or 'подобрать лучший рецепт на сегодня'}\n"
            f"Ограничения пользователя: {restrictions or 'нет'}\n"
            f"Нужно предложить не более {max_recipes} рецептов.\n\n"
            "Продукты в холодильнике:\n"
            f"{chr(10).join(inventory_lines) if inventory_lines else '- холодильник пуст'}\n\n"
            "Подходящие рецепты из базы:\n"
            f"{chr(10).join(recipe_lines) if recipe_lines else '- в базе нет хороших совпадений'}\n\n"
            "Сделай полезный и практичный ответ. "
            "Но обязательно: use_first, missing_ingredients, substitutions и steps "
            "верни именно как JSON-массивы строк."
        )

    def _to_list(self, value: Any) -> List[str]:
        if value is None:
            return []

        if isinstance(value, list):
            result = []
            for item in value:
                if item is None:
                    continue
                result.append(str(item).strip())
            return [x for x in result if x]

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []

            if "\n" in text:
                parts = [p.strip(" -•\t") for p in text.splitlines()]
                return [p for p in parts if p]

            if "," in text:
                parts = [p.strip() for p in text.split(",")]
                return [p for p in parts if p]

            if ";" in text:
                parts = [p.strip() for p in text.split(";")]
                return [p for p in parts if p]

            return [text]

        return [str(value).strip()]

    def _normalize_llm_payload(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        recipes = raw.get("recipes", [])
        if not isinstance(recipes, list):
            recipes = []

        normalized_recipes = []
        for recipe in recipes:
            if not isinstance(recipe, dict):
                continue

            normalized_recipes.append(
                {
                    "title": str(recipe.get("title", "Без названия")).strip(),
                    "why_it_fits": str(recipe.get("why_it_fits", "")).strip(),
                    "use_first": self._to_list(recipe.get("use_first")),
                    "missing_ingredients": self._to_list(recipe.get("missing_ingredients")),
                    "substitutions": self._to_list(recipe.get("substitutions")),
                    "steps": self._to_list(recipe.get("steps")),
                    "prep_time_minutes": int(recipe.get("prep_time_minutes", 15) or 15),
                    "difficulty": str(recipe.get("difficulty", "medium")).strip(),
                    "calories_estimate": int(recipe.get("calories_estimate", 0) or 0),
                }
            )

        raw["summary"] = str(raw.get("summary", "")).strip()
        raw["best_choice"] = str(raw.get("best_choice", "")).strip()
        raw["general_advice"] = str(raw.get("general_advice", "")).strip()
        raw["recipes"] = normalized_recipes
        return raw

    def llm_assistant(
        self,
        family_id: int,
        goal: str = "",
        restrictions: str = "",
        max_recipes: int = 3,
    ) -> Dict[str, Any]:
        inventory = self.build_inventory_snapshot(family_id)
        suggestions = self.suggest_by_inventory(family_id, limit=5)

        if not inventory:
            return {
                "summary": "В холодильнике пока нет продуктов для персонального подбора рецептов.",
                "best_choice": "Сначала добавьте хотя бы 2–3 продукта в холодильник.",
                "general_advice": "После добавления продуктов ассистент сможет предложить рецепты и подсветить срочные ингредиенты.",
                "recipes": [],
                "_meta": {"provider": "local", "model": "no-inventory"},
            }

        if not self.llm_client.is_configured:
            raise RuntimeError("LLM API key is not configured")

        raw = self.llm_client.create_recipe_plan(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(
                inventory=inventory,
                db_recipe_candidates=suggestions,
                goal=goal,
                restrictions=restrictions,
                max_recipes=max_recipes,
            ),
        )

        raw = self._normalize_llm_payload(raw)

        raw["inventory"] = inventory
        raw["rule_based_candidates"] = [
            {
                "recipe_id": item["recipe"].id,
                "title": item["recipe"].title,
                "match_percentage": item["match_percentage"],
                "missing_ingredients": item["missing_ingredients"],
            }
            for item in suggestions
        ]
        return raw
