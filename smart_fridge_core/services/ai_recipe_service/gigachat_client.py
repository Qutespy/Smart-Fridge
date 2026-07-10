"""
Клиент GigaChat для генерации рецептов.

Импорт пакета `gigachat` отложен в `_call_gigachat`, чтобы:
- модуль грузился без установленной зависимости (тесты мокают `generate_recipe`);
- падение по `ImportError` превращалось в осмысленную ошибку 503.
"""
from __future__ import annotations

import json
import re
from typing import Iterable, Optional

from core.config import settings


_VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}

_MEAL_TYPE_LABELS_RU = {
    "breakfast": "завтрак",
    "lunch": "обед",
    "dinner": "ужин",
    "snack": "перекус",
}


class RecipeGenerationError(Exception):
    """Базовое исключение для ошибок ИИ-рецептов."""


class RecipeServiceUnavailable(RecipeGenerationError):
    """Сервис недоступен: пустой ключ, сетевая ошибка, timeout, ImportError."""


class RecipeFormatError(RecipeGenerationError):
    """ИИ вернул контент, который нельзя распарсить или провалидировать."""


SYSTEM_PROMPT = (
    "Ты — кулинарный ассистент. Твоя задача — предложить рецепт блюда из ингредиентов, "
    "которые есть у пользователя в холодильнике. Если каких-то ингредиентов не хватает, "
    "предложи замены и пометь, насколько они критичны.\n\n"
    "Отвечай ТОЛЬКО на русском языке.\n\n"
    "Ответ ВЕРНИ СТРОГО в формате JSON (без пояснений вне JSON, без markdown-обёрток ``` ```).\n\n"
    "ОБЯЗАТЕЛЬНЫЕ ПОЛЯ ОТВЕТА:\n"
    "- title: строка, название блюда.\n"
    "- description: строка, короткое описание в 1-2 предложения.\n"
    "- cuisine: строка, например \"русская\", \"итальянская\", \"азиатская\".\n"
    "- meal_type: ровно одно значение из: breakfast, lunch, dinner, snack. "
    "НЕ возвращай несколько значений через запятую или вертикальную черту — выбери одно.\n"
    "- cook_time_minutes: целое число (минуты).\n"
    "- difficulty: ровно одно значение из: easy, medium, hard. "
    "НЕ возвращай несколько вариантов — выбери одно.\n"
    "- servings: целое число (количество порций).\n"
    "- ingredients: массив объектов; каждый объект содержит:\n"
    "    name (строка, продукт в именительном падеже),\n"
    "    amount (строка, количество с единицей измерения),\n"
    "    critical (true/false — обязателен ли ингредиент),\n"
    "    substitutes (массив строк с возможными заменами, может быть пустым).\n"
    "- steps: массив строк, шаги приготовления.\n"
    "- notes: строка с дополнительным комментарием или null.\n\n"
    "Пример валидного ответа:\n"
    "{\n"
    '  "title": "Омлет с сыром",\n'
    '  "description": "Быстрый завтрак на сковороде.",\n'
    '  "cuisine": "европейская",\n'
    '  "meal_type": "breakfast",\n'
    '  "cook_time_minutes": 10,\n'
    '  "difficulty": "easy",\n'
    '  "servings": 2,\n'
    '  "ingredients": [\n'
    '    {"name": "яйца", "amount": "4 шт", "critical": true, "substitutes": []},\n'
    '    {"name": "сыр", "amount": "50 г", "critical": false, "substitutes": ["творог"]}\n'
    "  ],\n"
    '  "steps": ["Взбить яйца.", "Натереть сыр.", "Жарить 5 минут."],\n'
    '  "notes": null\n'
    "}"
)


def build_prompt(
    fridge_items: Iterable[tuple[str, str]],
    meal_type: Optional[str] = None,
    cuisine: Optional[str] = None,
    restrictions: Optional[list[str]] = None,
    exclude_titles: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Формирует пару (system_prompt, user_prompt)."""
    lines: list[str] = ["В моём холодильнике сейчас:"]
    for name, qty in fridge_items:
        lines.append(f"- {name} ({qty})")

    lines.append("")
    lines.append("Параметры:")
    if meal_type:
        label = _MEAL_TYPE_LABELS_RU.get(meal_type, meal_type)
        lines.append(f"- Тип приёма пищи: {label}")
    else:
        lines.append("- Тип приёма пищи: любой")

    lines.append(f"- Кухня: {cuisine if cuisine else 'любая'}")

    if restrictions:
        lines.append(f"- Ограничения: {', '.join(restrictions)}")
    else:
        lines.append("- Ограничения: нет")

    if exclude_titles:
        lines.append("")
        lines.append(
            "Уже были предложены такие рецепты — НЕ повторяй их и не давай похожие "
            "блюда (другая основа, другая техника приготовления, другая категория):"
        )
        for t in exclude_titles:
            lines.append(f"- {t}")

    lines.append("")
    lines.append("Предложи один рецепт.")

    return SYSTEM_PROMPT, "\n".join(lines)


def parse_response(raw_text: str) -> dict:
    """
    Пытается извлечь JSON из ответа модели:
    1) снимает обёртку ```json ... ```;
    2) пробует json.loads напрямую;
    3) если упало — ищет первый {...}-блок и парсит его.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise RecipeFormatError("Пустой ответ ИИ")

    cleaned = raw_text.strip()
    # снимаем markdown-обёртку
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise RecipeFormatError(f"В ответе ИИ нет JSON-объекта: {raw_text[:200]!r}")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise RecipeFormatError(f"JSON битый: {e}; текст: {raw_text[:200]!r}") from e


def _normalize_enum(value, allowed: set[str]) -> str:
    """
    Если LLM вернула несколько вариантов через `|`, `,` или `/`
    (типа "lunch|dinner"), выбираем первый, который входит в допустимые.
    Возвращает оригинал, если ничего нормализовать не получилось.
    """
    if not isinstance(value, str):
        return value
    if value in allowed:
        return value
    candidates = re.split(r"[|,/]", value)
    for c in candidates:
        c = c.strip().lower()
        if c in allowed:
            return c
    return value


def validate_recipe(data: dict) -> None:
    """Бросает RecipeFormatError, если структура не соответствует контракту."""
    if not isinstance(data, dict):
        raise RecipeFormatError("Ответ ИИ — не объект")

    # мягкая нормализация: если модель прислала "lunch|dinner" — возьмём lunch
    if isinstance(data.get("meal_type"), str):
        data["meal_type"] = _normalize_enum(data["meal_type"], _VALID_MEAL_TYPES)
    if isinstance(data.get("difficulty"), str):
        data["difficulty"] = _normalize_enum(data["difficulty"], _VALID_DIFFICULTIES)

    required = {
        "title": str,
        "description": str,
        "cuisine": str,
        "meal_type": str,
        "cook_time_minutes": int,
        "difficulty": str,
        "servings": int,
        "ingredients": list,
        "steps": list,
    }
    for field, expected_type in required.items():
        if field not in data:
            raise RecipeFormatError(f"Нет обязательного поля '{field}'")
        # bool — это подкласс int, отсекаем явно для числовых полей
        if expected_type is int and isinstance(data[field], bool):
            raise RecipeFormatError(f"Поле '{field}' должно быть целым числом, а не bool")
        if not isinstance(data[field], expected_type):
            raise RecipeFormatError(
                f"Поле '{field}' должно быть {expected_type.__name__}, а не {type(data[field]).__name__}"
            )

    if data["meal_type"] not in _VALID_MEAL_TYPES:
        raise RecipeFormatError(
            f"meal_type='{data['meal_type']}' не входит в {sorted(_VALID_MEAL_TYPES)}"
        )
    if data["difficulty"] not in _VALID_DIFFICULTIES:
        raise RecipeFormatError(
            f"difficulty='{data['difficulty']}' не входит в {sorted(_VALID_DIFFICULTIES)}"
        )

    if not data["ingredients"]:
        raise RecipeFormatError("Список ингредиентов пуст")

    for i, ing in enumerate(data["ingredients"]):
        if not isinstance(ing, dict):
            raise RecipeFormatError(f"ingredients[{i}] — не объект")
        for f in ("name", "amount"):
            if f not in ing or not isinstance(ing[f], str):
                raise RecipeFormatError(f"ingredients[{i}].{f} отсутствует или не строка")
        if "critical" not in ing or not isinstance(ing["critical"], bool):
            raise RecipeFormatError(f"ingredients[{i}].critical отсутствует или не bool")
        subs = ing.get("substitutes", [])
        if not isinstance(subs, list) or not all(isinstance(s, str) for s in subs):
            raise RecipeFormatError(f"ingredients[{i}].substitutes должен быть списком строк")

    if not all(isinstance(s, str) for s in data["steps"]):
        raise RecipeFormatError("steps должен быть списком строк")
    if not data["steps"]:
        raise RecipeFormatError("Список шагов пуст")

    if "notes" in data and data["notes"] is not None and not isinstance(data["notes"], str):
        raise RecipeFormatError("notes должен быть строкой или null")


def _call_gigachat(system_prompt: str, user_prompt: str) -> str:
    """Один синхронный вызов GigaChat. Возвращает сырой контент сообщения."""
    try:
        from gigachat import GigaChat
    except ImportError as e:
        raise RecipeServiceUnavailable(
            "Пакет gigachat не установлен. Выполни: pip install gigachat"
        ) from e

    try:
        with GigaChat(
            credentials=settings.GIGACHAT_CREDENTIALS,
            scope=settings.GIGACHAT_SCOPE,
            model=settings.GIGACHAT_MODEL,
            verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL,
            timeout=settings.GIGACHAT_TIMEOUT_SECONDS,
        ) as giga:
            response = giga.chat({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.9,
            })
    except Exception as e:
        raise RecipeServiceUnavailable(f"GigaChat недоступен: {e}") from e

    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as e:
        raise RecipeFormatError(f"Не удалось извлечь контент из ответа GigaChat: {e}") from e


def generate_recipe(
    fridge_items: Iterable[tuple[str, str]],
    meal_type: Optional[str] = None,
    cuisine: Optional[str] = None,
    restrictions: Optional[list[str]] = None,
    exclude_titles: Optional[list[str]] = None,
) -> dict:
    """
    Генерирует рецепт через GigaChat. Делает один retry, если первый ответ
    не валидируется. Возвращает dict, прошедший validate_recipe().

    Поднимает RecipeServiceUnavailable / RecipeFormatError при ошибках.
    """
    if not settings.GIGACHAT_CREDENTIALS:
        raise RecipeServiceUnavailable("GigaChat не настроен: пустой GIGACHAT_CREDENTIALS")

    system_prompt, user_prompt = build_prompt(
        fridge_items, meal_type, cuisine, restrictions, exclude_titles
    )

    raw = _call_gigachat(system_prompt, user_prompt)
    try:
        data = parse_response(raw)
        validate_recipe(data)
        return data
    except RecipeFormatError:
        retry_user_prompt = (
            user_prompt
            + "\n\nНАПОМИНАЮ: верни СТРОГО валидный JSON без пояснений и без markdown."
        )
        retry_raw = _call_gigachat(system_prompt, retry_user_prompt)
        try:
            data = parse_response(retry_raw)
            validate_recipe(data)
            return data
        except RecipeFormatError as e:
            raise RecipeFormatError(f"ИИ вернул некорректный ответ после retry: {e}") from e
