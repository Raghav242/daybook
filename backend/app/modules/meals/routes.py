from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.auth.dependencies import current_user
from app.modules.categories.routes import get_service as get_categories
from app.modules.meals.repository import MealsRepository
from app.modules.meals.schemas import (
    AdditionInput,
    AdditionResult,
    MealPlanInput,
    MealPlanOutput,
    Preview,
    PreviewInput,
    RecipeInput,
    RecipeOutput,
    RecipePage,
)
from app.modules.meals.service import MealsService

router = APIRouter(tags=["meals"])


def get_service(session: Session = Depends(get_session), user=Depends(current_user)):
    return MealsService(MealsRepository(session, user.id), get_categories(session, user))


@router.get("/recipes", response_model=RecipePage)
def list_recipes(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    service: MealsService = Depends(get_service),
):
    return service.list_recipes(offset, limit)


@router.get("/recipes/{record_id}", response_model=RecipeOutput)
def get_recipe(record_id: UUID, service: MealsService = Depends(get_service)):
    return service.get_recipe(record_id)


@router.post("/recipes", response_model=RecipeOutput, status_code=201)
def create_recipe(data: RecipeInput, service: MealsService = Depends(get_service)):
    return service.create_recipe(data)


@router.put("/recipes/{record_id}", response_model=RecipeOutput)
def update_recipe(record_id: UUID, data: RecipeInput, service: MealsService = Depends(get_service)):
    return service.update_recipe(record_id, data)


@router.delete("/recipes/{record_id}", status_code=204)
def delete_recipe(record_id: UUID, service: MealsService = Depends(get_service)):
    service.delete_recipe(record_id)
    return Response(status_code=204)


@router.get("/meal-plan", response_model=list[MealPlanOutput])
def list_meals(
    start: date,
    days: int = Query(7, ge=1, le=31),
    service: MealsService = Depends(get_service),
):
    return service.entries(start, days)


@router.post("/meal-plan", response_model=MealPlanOutput, status_code=201)
def create_meal(data: MealPlanInput, service: MealsService = Depends(get_service)):
    return service.create_entry(data)


@router.put("/meal-plan/{record_id}", response_model=MealPlanOutput)
def update_meal(record_id: UUID, data: MealPlanInput, service: MealsService = Depends(get_service)):
    return service.update_entry(record_id, data)


@router.delete("/meal-plan/{record_id}", status_code=204)
def delete_meal(record_id: UUID, service: MealsService = Depends(get_service)):
    service.delete_entry(record_id)
    return Response(status_code=204)


@router.post("/meal-plan/grocery-preview", response_model=Preview)
def grocery_preview(data: PreviewInput, service: MealsService = Depends(get_service)):
    """Compute scaled, merged grocery lines for review. Writes nothing."""
    return service.preview(data.entry_ids)


@router.post("/meal-plan/grocery-additions", response_model=AdditionResult)
def add_groceries(
    data: AdditionInput, response: Response, service: MealsService = Depends(get_service)
):
    """Add reviewed lines to groceries. Repeating a request_id never adds them again."""
    result = service.add_to_groceries(data)
    response.status_code = 201 if result["created"] else 200
    return result
