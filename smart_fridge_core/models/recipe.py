from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime

from core.database import Base


class RecipeModel(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=False)
    calories = Column(Integer, default=0)
    prep_time_minutes = Column(Integer, default=0)
    image_url = Column(String(500), nullable=True)
    difficulty = Column(String(20), default="medium")
    ingredients = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
