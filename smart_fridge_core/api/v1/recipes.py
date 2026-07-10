from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.database import get_db
from models.recipe import RecipeModel
from services.recipe_service.engine import RecipeEngine
from api.v1.auth import get_current_user

router = APIRouter()


class AssistantRequest(BaseModel):
    goal: str = Field(default="", max_length=300)
    restrictions: str = Field(default="", max_length=300)
    max_recipes: int = Field(default=3, ge=1, le=5)


@router.get("/")
def get_recipes(db: Session = Depends(get_db)):
    recipes = db.query(RecipeModel).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "instructions": r.instructions,
            "calories": r.calories,
            "prep_time_minutes": r.prep_time_minutes,
            "difficulty": r.difficulty,
            "ingredients": r.ingredients or [],
            "image_url": r.image_url,
        }
        for r in recipes
    ]


@router.get("/suggestions")
def get_suggestions(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.family_id:
        raise HTTPException(status_code=400, detail="User is not attached to a family")

    engine = RecipeEngine(db)
    suggestions = engine.suggest_by_inventory(current_user.family_id, limit)
    return [
        {
            "recipe": {
                "id": s["recipe"].id,
                "title": s["recipe"].title,
                "calories": s["recipe"].calories,
                "prep_time_minutes": s["recipe"].prep_time_minutes,
                "difficulty": s["recipe"].difficulty,
                "ingredients": s["recipe"].ingredients or [],
                "image_url": s["recipe"].image_url,
            },
            "match_percentage": s["match_percentage"],
            "missing_ingredients": s["missing_ingredients"],
        }
        for s in suggestions
    ]


@router.post("/assistant")
def recipe_assistant(
    payload: AssistantRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not current_user.family_id:
        raise HTTPException(status_code=400, detail="User is not attached to a family")

    engine = RecipeEngine(db)
    try:
        return engine.llm_assistant(
            family_id=current_user.family_id,
            goal=payload.goal,
            restrictions=payload.restrictions,
            max_recipes=payload.max_recipes,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@router.get("/{recipe_id}")
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    recipe = db.query(RecipeModel).filter(RecipeModel.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return {
        "id": recipe.id,
        "title": recipe.title,
        "instructions": recipe.instructions,
        "calories": recipe.calories,
        "prep_time_minutes": recipe.prep_time_minutes,
        "difficulty": recipe.difficulty,
        "ingredients": recipe.ingredients or [],
        "image_url": recipe.image_url,
    }
