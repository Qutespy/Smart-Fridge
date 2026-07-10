from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.database import engine, Base
from core.config import settings

import models  # noqa: F401 — register all ORM models with Base

from api.v1 import auth, inventory, recipes, shopping, devices, ai_recipes
from workers.expiration_checker import start_scheduler

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield


app = FastAPI(
    title="Smart Fridge API",
    description="Backend API for Smart Fridge Application",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(recipes.router, prefix="/api/v1/recipes", tags=["Recipes"])
app.include_router(shopping.router, prefix="/api/v1/shopping", tags=["Shopping"])
app.include_router(devices.router, prefix="/api/v1/devices", tags=["Devices"])
app.include_router(ai_recipes.router, prefix="/api/v1/ai-recipes", tags=["AI Recipes"])


@app.get("/")
async def root():
    return {"message": "Smart Fridge API is running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
